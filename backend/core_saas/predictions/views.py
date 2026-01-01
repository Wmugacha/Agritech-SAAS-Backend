import logging
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organizations.utils import get_request_organization
from subscriptions.utils import check_subscription_limit
from .models import SoilAnalysisJob
from .serializers import SoilAnalysisJobSerializer
from .tasks import analyze_soil_spectra

logger = logging.getLogger(__name__)

class SoilAnalysisViewSet(mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    
    serializer_class = SoilAnalysisJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_request_organization(self.request)
        if not org:
            return SoilAnalysisJob.objects.none()
        return SoilAnalysisJob.objects.filter(organization=org).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        logger.info(f"Incoming Prediction Request from User: {request.user.email}")

        org = get_request_organization(request)
        if not org:
            logger.warning("Creation blocked: No organization context.")
            return Response({"detail": "Organization context required"}, status=403)

        # 1. Enforce Subscription Limits
        allowed, reason = check_subscription_limit(org, "predictions")
        if not allowed:
            logger.warning(f"Limit Reached for {org.name}: {reason}")
            return Response(
                {"detail": "Usage limit exceeded.", "reason": reason}, 
                status=403
            )

        # 2. Validate & Save
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        job = serializer.save(
            organization=org,
            requested_by=request.user,
            status=SoilAnalysisJob.Status.PENDING
        )

        # 3. Offload to Celery
        logger.info(f"Enqueueing Job {job.id} to Celery...")
        analyze_soil_spectra.delay(job.id)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)