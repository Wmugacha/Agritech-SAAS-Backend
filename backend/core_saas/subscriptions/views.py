import json
import logging
from datetime import UTC, datetime

import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.utils import get_request_organization

from .models import StripeEvent, Subscription
from .serializers import SubscriptionSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

class SubscriptionDetailView(APIView):
    """
    Return the current organization's subscription details.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Subscription details",
        description="Returns subscription details for the current organisation",
        responses={
            200: SubscriptionSerializer
        }
    )
    def get(self, request):
        org = get_request_organization(request)
        if not org:
            return Response({"detail": "No organization found"}, status=403)

        try:
            subscription = org.subscription
        except Subscription.DoesNotExist:
            return Response({"detail": "Subscription data missing"}, status=500)

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create Stripe Checkout Session",
        description="Generates a Stripe hosted checkout URL to upgrade to the PRO plan.",
        request=None, # JSON body not required for this POST
        responses={
            200: inline_serializer(
                name='CheckoutSessionResponse',
                fields={
                    'checkout_url': serializers.URLField()
                }
            )
        }
    )
    def post(self, request):
        org = get_request_organization(request)
        if not org:
            return Response({"error": "Organization context required"}, status=400)

        # Get or create the subscription record
        _sub, _created = Subscription.objects.get_or_create(organization=org)

        try:
            # Create a Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price': settings.STRIPE_PRO_PRICE_ID, 
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                # Pass the Organization ID in the metadata so Stripe remembers who paid!
                client_reference_id=str(org.id),
                success_url=f"{settings.FRONTEND_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
            )
            
            # Return the URL to the frontend so it can redirect the user
            return Response({'checkout_url': checkout_session.url})
            
        except stripe.error.StripeError:
            logger.exception("Stripe checkout failed for org %s", org.id)
            return Response({"error": "Payment provider error. Try again."}, status=502)


# Stripe subscription statuses -> our status. Anything not listed is treated as INACTIVE.
# https://docs.stripe.com/api/subscriptions/object#subscription_object-status
STRIPE_STATUS_MAP = {
    "active": Subscription.Status.ACTIVE,
    "trialing": Subscription.Status.ACTIVE,
    "past_due": Subscription.Status.PAST_DUE,
    "unpaid": Subscription.Status.PAST_DUE,
}
STRIPE_ENDED_STATUSES = {"canceled", "incomplete_expired"}


def _period_end(stripe_sub):
    """current_period_end moved from the subscription to its items in newer Stripe API versions."""
    timestamp = stripe_sub.get("current_period_end")
    if timestamp is None:
        items = stripe_sub.get("items", {}).get("data", [])
        timestamp = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else None


def _downgrade_to_free(sub):
    sub.plan = Subscription.PlanType.FREE
    sub.status = Subscription.Status.ACTIVE
    sub.stripe_subscription_id = None
    sub.current_period_end = None
    sub.save()


def handle_checkout_completed(session):
    org_id = session.get("client_reference_id")
    if not org_id:
        logger.warning("checkout.session.completed without client_reference_id")
        return

    try:
        sub = Subscription.objects.get(organization__id=org_id)
    except Subscription.DoesNotExist:
        logger.error(f"Webhook Warning: Subscription for Org {org_id} not found.")
        return

    sub.plan = Subscription.PlanType.PRO
    sub.status = Subscription.Status.ACTIVE
    sub.stripe_customer_id = session.get("customer")
    sub.stripe_subscription_id = session.get("subscription")
    sub.save()
    logger.info(f"✅ SUCCESS: Upgraded Organization {org_id} to PRO plan!")


def handle_subscription_updated(stripe_sub):
    # Look up by the Stripe subscription id. After a cancellation we clear that id, so a
    # late "updated" event for the old subscription finds nothing and can't re-upgrade.
    sub = Subscription.objects.filter(stripe_subscription_id=stripe_sub["id"]).first()
    if sub is None:
        logger.warning(f"No subscription matches Stripe subscription {stripe_sub['id']}")
        return

    stripe_status = stripe_sub.get("status")
    if stripe_status in STRIPE_ENDED_STATUSES:
        _downgrade_to_free(sub)
        logger.info(f"Organization {sub.organization_id} downgraded to FREE ({stripe_status})")
        return

    sub.status = STRIPE_STATUS_MAP.get(stripe_status, Subscription.Status.INACTIVE)
    sub.current_period_end = _period_end(stripe_sub)
    sub.save()
    logger.info(f"Organization {sub.organization_id} subscription is now {sub.status} ({stripe_status})")


def handle_subscription_deleted(stripe_sub):
    sub = Subscription.objects.filter(stripe_subscription_id=stripe_sub["id"]).first()
    if sub is None:
        logger.warning(f"No subscription matches Stripe subscription {stripe_sub['id']}")
        return

    _downgrade_to_free(sub)
    logger.info(f"Organization {sub.organization_id} cancelled; downgraded to FREE")


EVENT_HANDLERS = {
    "checkout.session.completed": handle_checkout_completed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
}


@csrf_exempt
def stripe_webhook(request):
    """
    Listens for Stripe events, verifies the signature, and keeps the plan in sync.
    Idempotent: each Stripe event id is processed at most once.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        # 1. Cryptographically verify the event came from Stripe
        stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        # Invalid payload
        logger.error("Webhook Error: Invalid payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        logger.error("Webhook Error: Invalid signature")
        return HttpResponse(status=400)

    # The signature is valid, so the raw JSON is trustworthy; plain dicts are easier to work with
    event = json.loads(payload)
    handler = EVENT_HANDLERS.get(event["type"])

    try:
        with transaction.atomic():
            # 2. Record the event id first. The primary key makes a second delivery fail here.
            # It's the same transaction as the handler, so if handling crashes the id is rolled
            # back too, and Stripe's automatic retry gets processed normally.
            StripeEvent.objects.create(id=event["id"], type=event["type"])

            # 3. Apply the change
            if handler:
                handler(event["data"]["object"])
    except IntegrityError:
        logger.info(f"Duplicate Stripe event {event['id']} ignored")

    return HttpResponse(status=200)