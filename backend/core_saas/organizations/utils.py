from organizations.models import Membership

def get_request_organization(request):
    """
    Safely resolve organization for both runtime and tests.
    """
    if hasattr(request, "organization"):
        return request.organization

    if request.user and request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user).first()
        if membership:
            return membership.organization

    return None

def get_request_role(request):
    """
    Safely resolve role for both runtime and tests.
    """
    if hasattr(request, "role"):
        return request.role

    if request.user and request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user).first()
        if membership:
            return membership.role

    return None
