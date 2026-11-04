import hashlib
import hmac
import json
import threading
import time
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from organizations.models import Membership
from predictions import tasks
from predictions.models import SoilAnalysisJob
from subscriptions import utils
from subscriptions.models import StripeEvent, Subscription

SUBSCRIPTION_URL = "/api/subscriptions/me/"
CHECKOUT_URL = "/api/subscriptions/checkout-session/"
WEBHOOK_URL = "/api/subscriptions/webhook/"
PREDICT_URL = "/api/predict/"
WEBHOOK_SECRET = "whsec_test_only"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stripe_settings(settings):
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    settings.STRIPE_PRO_PRICE_ID = "price_test_pro"
    settings.FRONTEND_URL = "https://app.example.com"


def signed_webhook(api_client, event, secret=WEBHOOK_SECRET):
    """Send a webhook signed exactly the way Stripe signs it, so the real verification code runs."""
    payload = json.dumps(event)
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return api_client.post(
        WEBHOOK_URL,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
    )


def checkout_completed(org_id):
    return {
        "id": "evt_test",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "object": "checkout.session",
                "client_reference_id": str(org_id),
                "customer": "cus_test123",
                "subscription": "sub_test123",
            }
        },
    }


class TestDefaultSubscription:
    def test_new_org_gets_free_active_subscription(self, org):
        org.refresh_from_db()

        assert org.subscription.plan == Subscription.PlanType.FREE
        assert org.subscription.status == Subscription.Status.ACTIVE
        assert org.subscription.limits["predictions"] == 10

    def test_subscription_endpoint_shows_plan_and_limits(self, client_for, owner):
        response = client_for(owner).get(SUBSCRIPTION_URL)

        assert response.status_code == 200
        assert response.data["plan"] == "FREE"
        assert response.data["limits"] == {"predictions": 10, "storage_mb": 100}

    def test_subscription_endpoint_requires_org(self, client_for, django_user_model):
        loner = django_user_model.objects.create_user(email="loner@example.com", password="x")

        assert client_for(loner).get(SUBSCRIPTION_URL).status_code == 403


class TestCheckout:
    def test_creates_stripe_session_for_my_org(self, client_for, org, owner):
        with mock.patch("subscriptions.views.stripe.checkout.Session.create") as create:
            create.return_value = mock.Mock(url="https://checkout.stripe.com/c/pay/cs_test")

            response = client_for(owner).post(CHECKOUT_URL)

        assert response.status_code == 200
        assert response.data == {"checkout_url": "https://checkout.stripe.com/c/pay/cs_test"}
        kwargs = create.call_args.kwargs
        assert kwargs["client_reference_id"] == str(org.id)
        assert kwargs["line_items"] == [{"price": "price_test_pro", "quantity": 1}]
        assert kwargs["mode"] == "subscription"
        assert kwargs["success_url"].startswith("https://app.example.com/dashboard")

    def test_requires_auth(self, api_client):
        assert api_client.post(CHECKOUT_URL).status_code == 401


class TestStripeWebhook:
    def test_checkout_completed_upgrades_org_to_pro(self, api_client, org):
        response = signed_webhook(api_client, checkout_completed(org.id))

        assert response.status_code == 200
        sub = Subscription.objects.get(organization=org)
        assert sub.plan == Subscription.PlanType.PRO
        assert sub.stripe_customer_id == "cus_test123"
        assert sub.stripe_subscription_id == "sub_test123"

    def test_bad_signature_is_rejected_and_nothing_changes(self, api_client, org):
        response = signed_webhook(api_client, checkout_completed(org.id), secret="whsec_attacker")

        assert response.status_code == 400
        assert Subscription.objects.get(organization=org).plan == Subscription.PlanType.FREE

    def test_missing_signature_is_rejected(self, api_client, org):
        response = api_client.post(
            WEBHOOK_URL, data=json.dumps(checkout_completed(org.id)), content_type="application/json"
        )

        assert response.status_code == 400

    def test_unrelated_events_are_acknowledged_and_ignored(self, api_client, org):
        event = {**checkout_completed(org.id), "type": "invoice.paid"}

        response = signed_webhook(api_client, event)

        assert response.status_code == 200
        assert Subscription.objects.get(organization=org).plan == Subscription.PlanType.FREE


class TestPredictionQuota:
    """FREE allows 10 billable predictions per calendar month, PRO allows 1000."""

    @pytest.fixture(autouse=True)
    def no_celery(self):
        with mock.patch.object(tasks.analyze_soil_spectra, "delay"):
            yield

    def submit(self, client):
        return client.post(PREDICT_URL, {"spectra": [0.45] * 2380}, format="json")

    def use_quota(self, org, count, **fields):
        return [SoilAnalysisJob.objects.create(organization=org, spectra=[], **fields) for _ in range(count)]

    def test_free_plan_allows_up_to_limit(self, client_for, org, owner):
        self.use_quota(org, 9)

        assert self.submit(client_for(owner)).status_code == 201

    def test_free_plan_blocks_when_limit_reached(self, client_for, org, owner):
        self.use_quota(org, 10)

        response = self.submit(client_for(owner))

        assert response.status_code == 403
        assert response.data["detail"] == "Usage limit exceeded."
        assert SoilAnalysisJob.objects.count() == 10

    def test_failed_jobs_do_not_count(self, client_for, org, owner):
        self.use_quota(org, 10, is_billable=False, status=SoilAnalysisJob.Status.FAILED)

        assert self.submit(client_for(owner)).status_code == 201

    def test_last_months_jobs_do_not_count(self, client_for, org, owner):
        jobs = self.use_quota(org, 10)
        # created_at is auto_now_add, so backdate with update()
        SoilAnalysisJob.objects.filter(id__in=[j.id for j in jobs]).update(
            created_at=timezone.now().replace(day=1) - timedelta(days=1)
        )

        assert self.submit(client_for(owner)).status_code == 201

    def test_other_orgs_usage_does_not_count(self, client_for, owner, other_org):
        self.use_quota(other_org, 10)

        assert self.submit(client_for(owner)).status_code == 201

    def test_pro_plan_has_higher_limit(self, client_for, org, owner):
        Subscription.objects.filter(organization=org).update(plan=Subscription.PlanType.PRO)
        self.use_quota(org, 10)

        assert self.submit(client_for(owner)).status_code == 201

    def test_inactive_subscription_is_blocked(self, client_for, org, make_member):
        Subscription.objects.filter(organization=org).update(status=Subscription.Status.PAST_DUE)
        agronomist = make_member(org, Membership.AGRONOMIST)

        response = self.submit(client_for(agronomist))

        assert response.status_code == 403
        assert response.data["reason"] == "Subscription is not active"


class TestQuotaConcurrency:
    """Two submits racing for the last free slot: exactly one may win."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_submits_cannot_both_take_the_last_slot(self, org, owner):
        SoilAnalysisJob.objects.bulk_create(SoilAnalysisJob(organization=org, spectra=[]) for _ in range(9))
        real_usage = utils.get_monthly_usage

        def slow_usage(*args, **kwargs):
            used = real_usage(*args, **kwargs)
            # Widen the race window: without a lock both requests read 9 here
            time.sleep(0.5)
            return used

        status_codes = []

        def submit():
            try:
                client = APIClient()
                client.force_authenticate(user=owner)
                response = client.post(PREDICT_URL, {"spectra": [0.45] * 2380}, format="json")
                status_codes.append(response.status_code)
            finally:
                # Each thread opens its own DB connection; close it so the test DB can be dropped
                connection.close()

        with mock.patch.object(utils, "get_monthly_usage", slow_usage), mock.patch.object(
            tasks.analyze_soil_spectra, "delay"
        ):
            threads = [threading.Thread(target=submit) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert sorted(status_codes) == [201, 403]
        assert SoilAnalysisJob.objects.filter(organization=org).count() == 10


STRIPE_EVENTS_DIR = Path(__file__).parent / "test_data" / "stripe"


def stored_event(name, **object_overrides):
    """Load a stored Stripe event payload, optionally overriding fields on data.object."""
    event = json.loads((STRIPE_EVENTS_DIR / f"{name}.json").read_text())
    event["data"]["object"].update(object_overrides)
    return event


@pytest.fixture
def pro_sub(org):
    sub = Subscription.objects.get(organization=org)
    sub.plan = Subscription.PlanType.PRO
    sub.stripe_customer_id = "cus_test123"
    sub.stripe_subscription_id = "sub_test123"
    sub.save()
    return sub


class TestSubscriptionLifecycleWebhooks:
    def test_payment_failure_marks_subscription_past_due(self, api_client, pro_sub):
        response = signed_webhook(api_client, stored_event("customer.subscription.updated"))

        assert response.status_code == 200
        pro_sub.refresh_from_db()
        assert pro_sub.status == Subscription.Status.PAST_DUE
        assert pro_sub.plan == Subscription.PlanType.PRO
        # Read from items[0], where newer Stripe API versions put it
        assert pro_sub.current_period_end.timestamp() == 1793078400

    def test_past_due_org_cannot_submit_predictions(self, api_client, client_for, owner, pro_sub):
        signed_webhook(api_client, stored_event("customer.subscription.updated"))

        with mock.patch.object(tasks.analyze_soil_spectra, "delay"):
            response = client_for(owner).post(PREDICT_URL, {"spectra": [0.45] * 2380}, format="json")

        assert response.status_code == 403
        assert response.data["reason"] == "Subscription is not active"

    def test_payment_recovery_reactivates(self, api_client, pro_sub):
        pro_sub.status = Subscription.Status.PAST_DUE
        pro_sub.save()

        signed_webhook(api_client, stored_event("customer.subscription.updated", status="active"))

        pro_sub.refresh_from_db()
        assert pro_sub.status == Subscription.Status.ACTIVE

    def test_cancellation_downgrades_to_free(self, api_client, pro_sub):
        response = signed_webhook(api_client, stored_event("customer.subscription.deleted"))

        assert response.status_code == 200
        pro_sub.refresh_from_db()
        assert pro_sub.plan == Subscription.PlanType.FREE
        assert pro_sub.status == Subscription.Status.ACTIVE
        assert pro_sub.stripe_subscription_id is None
        assert pro_sub.limits["predictions"] == 10

    def test_late_update_after_cancellation_does_not_reupgrade(self, api_client, pro_sub):
        signed_webhook(api_client, stored_event("customer.subscription.deleted"))

        # Stripe doesn't guarantee delivery order
        signed_webhook(api_client, stored_event("customer.subscription.updated", status="active"))

        pro_sub.refresh_from_db()
        assert pro_sub.plan == Subscription.PlanType.FREE

    def test_unknown_stripe_subscription_is_acknowledged(self, api_client, pro_sub):
        response = signed_webhook(api_client, stored_event("customer.subscription.deleted", id="sub_unknown"))

        assert response.status_code == 200
        pro_sub.refresh_from_db()
        assert pro_sub.plan == Subscription.PlanType.PRO


class TestWebhookIdempotency:
    def test_same_event_delivered_twice_is_processed_once(self, api_client, pro_sub):
        event = stored_event("customer.subscription.deleted")
        signed_webhook(api_client, event)
        # Simulate a later re-upgrade, then a duplicate delivery of the old cancellation
        pro_sub.refresh_from_db()
        pro_sub.plan = Subscription.PlanType.PRO
        pro_sub.stripe_subscription_id = "sub_test123"
        pro_sub.save()

        response = signed_webhook(api_client, event)

        assert response.status_code == 200
        pro_sub.refresh_from_db()
        assert pro_sub.plan == Subscription.PlanType.PRO
        assert StripeEvent.objects.filter(id=event["id"]).count() == 1

    def test_failed_handler_does_not_record_event_so_stripe_can_retry(self, pro_sub):
        client = APIClient(raise_request_exception=False)
        event = stored_event("customer.subscription.deleted")

        with mock.patch.dict(
            "subscriptions.views.EVENT_HANDLERS",
            {"customer.subscription.deleted": mock.Mock(side_effect=RuntimeError("boom"))},
        ):
            response = signed_webhook(client, event)

        assert response.status_code == 500
        assert not StripeEvent.objects.filter(id=event["id"]).exists()

        # Stripe retries; this time the handler works
        assert signed_webhook(client, event).status_code == 200
        pro_sub.refresh_from_db()
        assert pro_sub.plan == Subscription.PlanType.FREE