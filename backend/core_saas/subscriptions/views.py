import stripe
import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organizations.utils import get_request_organization
from .serializers import SubscriptionSerializer
from .models import Subscription
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, inline_serializer

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
        sub, created = Subscription.objects.get_or_create(organization=org)

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
                success_url=settings.FRONTEND_URL + '/dashboard?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=settings.FRONTEND_URL + '/pricing',
            )
            
            # Return the URL to the frontend so it can redirect the user
            return Response({'checkout_url': checkout_session.url})
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)

@csrf_exempt
def stripe_webhook(request):
    """
    Listens for Stripe events, verifies the signature, and provisions the Pro tier.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        # 1. Cryptographically verify the event came from Stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error("Webhook Error: Invalid payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error("Webhook Error: Invalid signature")
        return HttpResponse(status=400)

    # 2. Handle the specific "checkout successful" event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Retrieve Org ID
        org_id = session.get('client_reference_id')
        
        # Extract the Stripe IDs for future recurring billing logic
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        if org_id:
            try:
                # 3. Find the user's Subscription record and UPGRADE THEM!
                sub = Subscription.objects.get(organization__id=org_id)
                sub.plan = 'PRO'
                sub.stripe_customer_id = customer_id
                sub.stripe_subscription_id = subscription_id
                sub.save()
                
                logger.info(f"✅ SUCCESS: Upgraded Organization {org_id} to PRO plan!")
            except Subscription.DoesNotExist:
                logger.error(f"Webhook Warning: Subscription for Org {org_id} not found.")

    return HttpResponse(status=200)