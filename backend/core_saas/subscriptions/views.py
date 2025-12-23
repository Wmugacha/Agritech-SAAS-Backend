from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organizations.utils import get_request_organization
from .serializers import SubscriptionSerializer
from .models import Subscription

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