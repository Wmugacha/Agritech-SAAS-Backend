import logging

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from organizations.permissions import RoleBasedPermissionsMixin
from organizations.utils import get_request_organization, get_request_role

from .models import CropSeason, Farm, FarmActivity, Field
from .serializers import (
    CropSeasonSerializer,
    FarmActivitySerializer,
    FarmSerializer,
    FieldSerializer,
)

logger = logging.getLogger(__name__)


class FarmViewSet(RoleBasedPermissionsMixin, viewsets.ModelViewSet):
    serializer_class = FarmSerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)

        if not org:
            return Farm.objects.none()

        base_qs = Farm.objects.filter(organization=org).order_by("-created_at")

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
        
        # Owner defaults to the person creating it; the serializer only accepts members of this org
        owner = serializer.validated_data.get("owner") or self.request.user
        serializer.save(organization=org, owner=owner)


class FieldViewSet(RoleBasedPermissionsMixin, viewsets.ModelViewSet):
    serializer_class = FieldSerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        if not org:
            return Field.objects.none()   

        base_qs = Field.objects.filter(farm__organization=org).order_by("-created_at")

        # If Admin/Agronomist, see ALL fields in the org
        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
        
        # If Farmer, see ONLY fields on farms they own
        return base_qs.filter(farm__owner=self.request.user)
    

class CropSeasonViewSet(RoleBasedPermissionsMixin, viewsets.ModelViewSet):
    serializer_class = CropSeasonSerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        
        if not org:
            return CropSeason.objects.none()

        base_qs = CropSeason.objects.filter(field__farm__organization=org).order_by("-created_at")

        # Admin/Agronomist see all
        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
            
        # Farmers only see seasons on their own farms
        return base_qs.filter(field__farm__owner=self.request.user)


class FarmActivityViewSet(RoleBasedPermissionsMixin, viewsets.ModelViewSet):
    serializer_class = FarmActivitySerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        role = get_request_role(self.request)
        
        if not org:
            return FarmActivity.objects.none()

        base_qs = FarmActivity.objects.filter(season__field__farm__organization=org).order_by("-created_at")

        if role in ['OWNER', 'ORG_ADMIN', 'AGRONOMIST']:
            return base_qs
            
        return base_qs.filter(season__field__farm__owner=self.request.user)
