from organizations.models import Membership

def get_request_organization(request):
    # 1. Check if already there
    if hasattr(request, "organization") and request.organization is not None:
        return request.organization

    # 2. If not, find it and ATTACH it
    if request.user and request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user).first()
        if membership:
            # This 'patches' the request for the rest of the test/request cycle
            request.organization = membership.organization
            return request.organization

    return None

def get_request_role(request):
    # 1. Check if already there
    if hasattr(request, "role") and request.role is not None:
        return request.role

    # 2. If not, find it and ATTACH it
    if request.user and request.user.is_authenticated:
        org = get_request_organization(request)
        membership = Membership.objects.filter(
            user=request.user,
            organization=org
        ).first()

        if membership:
            request.role = membership.role
            return request.role

    return None