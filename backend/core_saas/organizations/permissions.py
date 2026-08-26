from rest_framework.permissions import BasePermission
from .models import Membership
from .utils import get_request_role

class BaseOrgPermission(BasePermission):
    """
    Base permission that safely resolves role
    even if middleware did not run (for tests).
    Superusers automatically pass permission checks.
    """

    def get_role(self, request):
        return get_request_role(request)

    def is_superuser(self, request):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsOrgAdmin(BaseOrgPermission):
    def has_permission(self, request, view):
        if self.is_superuser(request):
            return True
        return self.get_role(request) in [Membership.OWNER, Membership.ORG_ADMIN]


class IsAgronomistOrAdmin(BaseOrgPermission):
    def has_permission(self, request, view):
        if self.is_superuser(request):
            return True
        return self.get_role(request) in [
            Membership.OWNER,
            Membership.ORG_ADMIN,
            Membership.AGRONOMIST,
        ]


class IsViewerOrAbove(BaseOrgPermission):
    def has_permission(self, request, view):
        if self.is_superuser(request):
            return True
        return self.get_role(request) in [
            Membership.OWNER,
            Membership.ORG_ADMIN,
            Membership.AGRONOMIST,
            Membership.VIEWER,
        ]

