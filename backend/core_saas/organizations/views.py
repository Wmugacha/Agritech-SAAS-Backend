from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import OrganizationSerializer
from organizations.permissions import IsAgronomistOrAdmin
from .utils import get_request_organization


class CurrentOrganizationView(APIView):
    """
    Returns the organization of the current request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Use the utility to safely get the org
        org = get_request_organization(request)
        
        # 2. Handle the case where the user has NO organization
        if not org:
            return Response(
                {"detail": "User is not assigned to an organization."}, 
                status=404
            )
            
        serializer = OrganizationSerializer(org)
        return Response(serializer.data)


class DemoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAgronomistOrAdmin]

    def initial(self, request, *args, **kwargs):
        # Resolve the organization and attach it to the request
        # This ensures get_request_role() in permissions finds the right data
        request.organization = get_request_organization(request)
        
        # To let DRF run the permission checks
        super().initial(request, *args, **kwargs)

    def post(self, request):
        return Response({"detail": "Created"}, status=201)
    
    def put(self, request): # To fix the Admin test failure
        return Response({"detail": "Updated"}, status=200)
