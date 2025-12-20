from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import OrganizationSerializer
from organizations.permissions import IsAgronomistOrAdmin


class CurrentOrganizationView(APIView):
    """
    Returns the organization of the current request.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = OrganizationSerializer(request.organization)
        return Response(serializer.data)

class DemoCreateView(APIView):
    """
    Minimal endpoint to validate RBAC behavior.
    """

    permission_classes = [IsAuthenticated, IsAgronomistOrAdmin]

    def post(self, request):
        return Response({"detail": "Created"}, status=201)
