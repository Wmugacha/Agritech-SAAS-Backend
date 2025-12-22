from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from organizations.permissions import (
    IsAgronomistOrAdmin,
    IsViewerOrAbove,
)
from .models import SoilSample
from organizations.models import Membership
from .serializers import SoilSampleSerializer
from organizations.utils import get_request_organization


class SoilSampleViewSet(viewsets.ModelViewSet):
    serializer_class = SoilSampleSerializer

    def get_queryset(self):
        """
        Return only soil samples belonging to the user's organization.
        This is the core tenant isolation guarantee.
        """
        org = get_request_organization(self.request)

        if not org:
            return SoilSample.objects.none()

        return SoilSample.objects.filter(
            organization=org).select_related('uploaded_by')

    def get_permissions(self):
        """
        Apply RBAC rules per action.
        """
        if self.action == "create":
            return [IsAuthenticated(), IsAgronomistOrAdmin()]

        return [IsAuthenticated(), IsViewerOrAbove()]

    def perform_create(self, serializer):

        serializer.save(
            organization=get_request_organization(self.request),
            uploaded_by=self.request.user
        )
