import logging
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from organizations.utils import get_request_organization
from .models import Farm, Field
from .serializers import FarmSerializer, FieldSerializer
from organizations.models import Membership

logger = logging.getLogger(__name__)

class FarmViewSet(viewsets.ModelViewSet):
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_request_organization(self.request)
        if not org:
            return Farm.objects.none()

        user = self.request.user

        # 1. Get the User's Role in this Organization
        try:
            membership = Membership.objects.get(user=user, organization=org)
            user_role = membership.role
        except Membership.DoesNotExist:
            return Farm.objects.none()

        # 2. Logic: Who gets to see what?
        
        # SUPER USERS (Admin & Agronomist) -> See EVERYTHING in the Org
        if user_role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return Farm.objects.filter(organization=org)
        
        # REGULAR USERS (Farmers/Viewers) -> See ONLY their own farms
        else:
            return Farm.objects.filter(organization=org, owner=user)

    def perform_create(self, serializer):
        org = get_request_organization(self.request)
        if not org:
            raise PermissionDenied("Organization context required.")
        
        # Automatically set the 'owner' to the person creating it
        serializer.save(organization=org, owner=self.request.user)

class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_request_organization(self.request)
        if not org:
            return Field.objects.none()
        
        # 2. FIX: Apply the same "Owner vs Admin" logic to Fields
        user = self.request.user
        try:
            membership = Membership.objects.get(user=user, organization=org)
            user_role = membership.role
        except Membership.DoesNotExist:
            return Field.objects.none()

        # If Admin/Agronomist, see ALL fields in the org
        if user_role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return Field.objects.filter(farm__organization=org)
        
        # If Farmer, see ONLY fields on farms they own
        else:
            return Field.objects.filter(farm__organization=org, farm__owner=user)
    
    def perform_create(self, serializer):        
        # Get the farm the user is trying to add this field to
        target_farm = serializer.validated_data.get('farm')
        user = self.request.user
        
        # Check if the user owns that farm (unless they are an admin)
        org = get_request_organization(self.request)
        
        # Check if farm is in current org
        if target_farm.organization != org:
             raise PermissionDenied("Cannot add fields to a farm in a different organization.")

        # Check if user owns the farm OR is an Admin/Agronomist
        is_owner = target_farm.owner == user
        
        # Fetch role
        membership = Membership.objects.get(user=user, organization=org)
        is_privileged = membership.role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']

        if not is_owner and not is_privileged:
            raise PermissionDenied("You do not have permission to add fields to this farm.")

        serializer.save()