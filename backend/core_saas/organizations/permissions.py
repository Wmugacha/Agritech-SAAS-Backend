from rest_framework.permissions import BasePermission
from organizations.models import Membership


class BaseOrgPermission(BasePermission):
    """
    Base permission that safely resolves role
    even if middleware did not run (for tests).
    """

    def get_role(self, request):
        # Middleware path (normal requests)
        if hasattr(request, "role"):
            return request.role

        # Fallback path (tests / edge cases)
        if request.user and request.user.is_authenticated:
            try:
                membership = Membership.objects.get(user=request.user)
                return membership.role
            except Membership.DoesNotExist:
                return None

        return None


class IsOrgAdmin(BaseOrgPermission):
    def has_permission(self, request, view):
        return self.get_role(request) == Membership.ORG_ADMIN


class IsAgronomistOrAdmin(BaseOrgPermission):
    def has_permission(self, request, view):
        return self.get_role(request) in [
            Membership.ORG_ADMIN,
            Membership.AGRONOMIST,
        ]


class IsViewerOrAbove(BaseOrgPermission):
    def has_permission(self, request, view):
        return self.get_role(request) in [
            Membership.ORG_ADMIN,
            Membership.AGRONOMIST,
            Membership.VIEWER,
        ]
