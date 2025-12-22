from rest_framework.permissions import BasePermission
from .models import Membership
from .utils import get_request_role

class BaseOrgPermission(BasePermission):
    """
    Base permission that safely resolves role
    even if middleware did not run (for tests).
    """

    def get_role(self, request):
        return get_request_role(request)


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
