import logging
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from organizations.utils import get_request_organization, get_request_role
from .models import Farm, Field, CropSeason, FarmActivity
from .serializers import FarmSerializer, FieldSerializer, CropSeasonSerializer, FarmActivitySerializer
from organizations.models import Membership

logger = logging.getLogger(__name__)

class FarmViewSet(viewsets.ModelViewSet):
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)

        if not org:
            return Farm.objects.none()

        base_qs = Farm.objects.filter(organization=org)

        # 2. Logic: Who gets to see what?
        
        # SUPER USERS (Admin & Agronomist) -> See EVERYTHING in the Org
        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
        
        # REGULAR USERS (Farmers/Viewers) -> See ONLY their own farms
        return base_qs.filter(owner=self.request.user)

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
        role = get_request_role(self.request)
        if not org:
            return Field.objects.none()   

        base_qs = Field.objects.filter(farm__organization=org)

        # If Admin/Agronomist, see ALL fields in the org
        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
        
        # If Farmer, see ONLY fields on farms they own
        return base_qs.filter(farm__owner=self.request.user)
    
    def perform_create(self, serializer):        
        # Get the farm the user is trying to add this field to
        target_farm = serializer.validated_data.get('farm')
        user = self.request.user
        
        # Check if the user owns that farm (unless they are an admin)
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        
        # Check if farm is in current org
        if target_farm.organization != org:
             raise PermissionDenied("Cannot add fields to a farm in a different organization.")

        # Check if user owns the farm OR is an Admin/Agronomist
        is_owner = target_farm.owner == user
        is_privileged = role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']

        if not is_owner and not is_privileged:
            raise PermissionDenied("You do not have permission to add fields to this farm.")

        serializer.save()

class CropSeasonViewSet(viewsets.ModelViewSet):
    serializer_class = CropSeasonSerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        
        if not org:
            return CropSeason.objects.none()

        base_qs = CropSeason.objects.filter(field__farm__organization=org)

        # Admin/Agronomist see all
        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
            
        # Farmers only see seasons on their own farms
        return base_qs.filter(field__farm__owner=self.request.user)

    def perform_create(self, serializer):
        target_field = serializer.validated_data.get('field')
        user = self.request.user
        org = get_request_organization(self.request)
        role = get_request_role(self.request)

        if target_field.farm.organization != org:
            raise PermissionDenied("Cannot add season to a field in a different organization.")

        is_owner = target_field.farm.owner == user
        is_privileged = role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']

        if not is_owner and not is_privileged:
            raise PermissionDenied("You do not have permission to add a season to this field.")

        serializer.save()


class FarmActivityViewSet(viewsets.ModelViewSet):
    serializer_class = FarmActivitySerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        
        if not org:
            return FarmActivity.objects.none()

        base_qs = FarmActivity.objects.filter(season__field__farm__organization=org)

        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
            
        return base_qs.filter(season__field__farm__owner=self.request.user)

    def perform_create(self, serializer):
        target_season = serializer.validated_data.get('season')
        user = self.request.user
        org = get_request_organization(self.request)
        role = get_request_role(self.request)

        if target_season.field.farm.organization != org:
            raise PermissionDenied("Cannot add activity to a season in a different organization.")

        is_owner = target_season.field.farm.owner == user
        is_privileged = role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']

        if not is_owner and not is_privileged:
            raise PermissionDenied("You do not have permission to add an activity to this season.")

        serializer.save()