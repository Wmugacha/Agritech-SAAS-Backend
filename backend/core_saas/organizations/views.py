from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Organization, Membership
from .serializers import OrganizationSerializer
from organizations.permissions import IsAgronomistOrAdmin
from .utils import get_request_organization
from subscriptions.models import Subscription
from drf_spectacular.utils import extend_schema
from rest_framework import serializers


class CreateOrganizationView(APIView):
    """
    Allows an authenticated user to create a new Organization and become its OWNER.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        if serializer.is_valid():
            org = serializer.save()
            # Assign creator as the OWNER
            Membership.objects.get_or_create(
                user=request.user,
                organization=org,
                role=Membership.OWNER
            )
            # Create a default FREE subscription
            Subscription.objects.get_or_create(
                organization=org,
                defaults={"plan": Subscription.PlanType.FREE, "status": Subscription.Status.ACTIVE}
            )
            return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentOrganizationView(APIView):
    """
    Returns the organization of the current request.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Organization details",
        description="Returns details for the current organisation",
        responses={
            200: OrganizationSerializer
        }
    )
    def get(self, request):
        # 1. Use the utility to safely get the org
        org = get_request_organization(request)
        
        # 2. Handle the case where the user has NO organization
        if not org:
            return Response(
                {"detail": "User is not assigned to an organization."}, 
                status=404
            )
            
        serializer = OrganizationSerializer(org)
        return Response(serializer.data)


class DemoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAgronomistOrAdmin]
    serializer_class = OrganizationSerializer

    def initial(self, request, *args, **kwargs):
        # Resolve the organization and attach it to the request
        # This ensures get_request_role() in permissions finds the right data
        request.organization = get_request_organization(request)
        
        # To let DRF run the permission checks
        super().initial(request, *args, **kwargs)

    def post(self, request):
        return Response({"detail": "Created"}, status=201)
    
    def put(self, request): # To fix the Admin test failure
        return Response({"detail": "Updated"}, status=200)

