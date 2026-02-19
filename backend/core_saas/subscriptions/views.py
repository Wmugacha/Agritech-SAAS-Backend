import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organizations.utils import get_request_organization
from .serializers import SubscriptionSerializer
from .models import Subscription

stripe.api_key = settings.STRIPE_SECRET_KEY

class SubscriptionDetailView(APIView):
    """
    Return the current organization's subscription details.
    """
    permission_classes = [IsAuthenticated]

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