import logging
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organizations.utils import get_request_organization
from subscriptions.utils import check_subscription_limit
from .models import SoilAnalysisJob
from .serializers import SoilAnalysisJobSerializer
from .tasks import analyze_soil_spectra
from django.utils import timezone
from django.db.models import Count, Avg, FloatField
from django.db.models.functions import Cast
from django.db.models.fields.json import KeyTextTransform
from rest_framework.views import APIView

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


class DashboardAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get the user's organization context
        org = get_request_organization(request)
        if not org:
            return Response({"error": "Organization context required"}, status=400)

        # Separate jobs belonging to this organization
        # Navigate the relationships: Job -> Field -> Farm -> Organization
        base_jobs = SoilAnalysisJob.objects.filter(field__farm__organization=org)

        # Time Filter: Jobs created this month
        current_month = timezone.now().month
        current_year = timezone.now().year
        jobs_this_month = base_jobs.filter(
            created_at__month=current_month, 
            created_at__year=current_year
        )

        # 4. Advanced Aggregation: Math inside the JSONField
        # - KeyTextTransform extracts the "SOM" value as text from the JSON
        # - Cast converts that text into a FloatField so we can do math on it
        # - Avg calculates the average of those floats
        som_stats = base_jobs.annotate(
            som_value=Cast(KeyTextTransform('SOM', 'predicted_properties'), output_field=FloatField())
        ).aggregate(
            average_som=Avg('som_value')
        )

        # 5. Grouping: Count jobs per status (e.g., SUCCESS vs FAILED)
        # We use standard value/annotate grouping here
        status_counts = list(base_jobs.values('status').annotate(total=Count('id')))

        # 6. Assemble the Dashboard Payload
        payload = {
            "total_samples_all_time": base_jobs.count(),
            "total_samples_this_month": jobs_this_month.count(),
            "average_som": round(som_stats['average_som'], 2) if som_stats['average_som'] else 0.0,
            "jobs_by_status": status_counts
        }

        return Response(payload)