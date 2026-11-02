import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from organizations.models import Membership
from predictions import tasks
from predictions.models import SoilAnalysisJob
from subscriptions.models import Subscription

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
