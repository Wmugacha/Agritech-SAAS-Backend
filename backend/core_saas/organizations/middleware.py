from django.http import JsonResponse
from .models import Membership

class OrganizationMiddleware:
    """
    Attaches organization + role to every authenticated request.
    """

    EXEMPT_PATHS = [
        "/admin/",
        "/api/auth/",
        "/api/docs/",
        "/api/schema/",
        "/api/organizations/create/",
        "/api/subscriptions/webhook/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize with None so the View doesn't crash
        request.organization = None
        request.role = None

        # Check if the path is exempt from organization requirement
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            if request.user.is_authenticated and request.user.is_superuser:
                request.role = Membership.ORG_ADMIN
            return self.get_response(request)

        # Only run for authenticated users
        if request.user.is_authenticated:
            try:
                membership = Membership.objects.select_related(
                    "organization"
                ).get(user=request.user)

                # Attach tenant context to request
                request.organization = membership.organization
                request.role = membership.role

            except Membership.DoesNotExist:
                return JsonResponse(
                    {"detail": "User is not assigned to an organization."},
                    status=403
                )

        return self.get_response(request)

