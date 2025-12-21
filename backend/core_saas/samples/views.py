from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from organizations.permissions import (
    IsAgronomistOrAdmin,
    IsViewerOrAbove,
)
from .models import SoilSample
from organizations.models import Membership
from .serializers import SoilSampleSerializer
from rest_framework.exceptions import PermissionDenied
from organizations.utils import get_request_organization


class SoilSampleViewSet(viewsets.ModelViewSet):
    serializer_class = SoilSampleSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        """
        Attach organization and role to the request
        BEFORE permissions are evaluated.
        """

        if request.user and request.user.is_authenticated:
            membership = Membership.objects.filter(user=request.user).first()
            if membership:
                request.organization = membership.organization
                request.role = membership.role
            else:
                request.organization = None
                request.role = None

        super().initial(request, *args, **kwargs)


    def get_queryset(self):
        """
        Return only soil samples belonging to the user's organization.
        This is the core tenant isolation guarantee.
        """
        org = get_request_organization(self.request)

        if not org:
            return SoilSample.objects.none()
        return SoilSample.objects.filter(organization=org)

    def get_permissions(self):
        """
        Apply RBAC rules per action.
        """
        if self.action == "create":
            permission_classes = [
                IsAuthenticated,
                IsAgronomistOrAdmin,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                IsViewerOrAbove,
            ]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Automatically assign organization and uploader.
        Prevents tenant spoofing.
        """

        org = get_request_organization(self.request)
        if not org:
            raise PermissionDenied("User is not part of any organization.")

        serializer.save(
            organization=org,
            uploaded_by=self.request.user,
        )
