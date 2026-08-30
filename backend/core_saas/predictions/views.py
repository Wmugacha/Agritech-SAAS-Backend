import logging
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
from rest_framework import viewsets, mixins, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from organizations.utils import get_request_organization
from subscriptions.utils import check_subscription_limit
from .models import SoilAnalysisJob
from .serializers import SoilAnalysisJobSerializer, SoilAnalysisJobListSerializer
from .tasks import analyze_soil_spectra
from django.utils import timezone
from django.db.models import Count, Avg, FloatField
from django.db.models.functions import Cast
from django.db.models.fields.json import KeyTextTransform
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, inline_serializer

logger = logging.getLogger(__name__)

# Standard 2,380 expected wavelengths across the spectral band (e.g. 3999.053 - 600.0723 cm⁻¹ / nm)
EXPECTED_WAVELENGTHS = np.linspace(3999.053, 600.0723, 2380)


def process_and_standardize_spectra(request_data, spectra_file=None):
    """
    Data Cleaning & Resampling Pipeline:
    1. Reads uploaded CSV or raw JSON array.
    2. Drops target columns like 'SOM' if present.
    3. Extracts incoming wavelength header values or infers them.
    4. Uses 1D linear interpolation (scipy.interpolate.interp1d) to resample
       features into exactly 2,380 standardized wavelengths matching the ML model.
    Returns a 2D list (list of sample lists).
    """
    if spectra_file:
        # Read file into DataFrame
        try:
            # Check if file has header row by attempting numeric conversion
            df = pd.read_csv(spectra_file)
            spectra_file.seek(0)
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise serializers.ValidationError({"spectra_file": "Invalid CSV file format."})

        # Drop target 'SOM' column if present (case-insensitive check)
        som_cols = [col for col in df.columns if str(col).strip().upper() == 'SOM']
        if som_cols:
            df = df.drop(columns=som_cols)

        # Try to parse column names as numeric wavelengths
        raw_cols = df.columns.tolist()
        try:
            incoming_wavelengths = np.array([float(str(col).strip()) for col in raw_cols])
        except ValueError:
            # Header row contained text or non-numeric labels; assume uniform spacing across columns
            num_cols = df.shape[1]
            incoming_wavelengths = np.linspace(3999.053, 600.0723, num_cols)

        # Extract spectral absorbance values
        feature_matrix = df.values.astype(float)
    else:
        # Raw JSON input provided
        raw_spectra = request_data.get('spectra')
        if not raw_spectra:
            raise serializers.ValidationError({"spectra": "Spectra data is required."})

        raw_array = np.array(raw_spectra, dtype=float)
        
        # Ensure 2D array: (n_samples, n_features)
        if raw_array.ndim == 1:
            feature_matrix = raw_array.reshape(1, -1)
        else:
            feature_matrix = raw_array

        num_cols = feature_matrix.shape[1]
        incoming_wavelengths = np.linspace(3999.053, 600.0723, num_cols)


    # Resample each sample row to 2,380 features if column count differs
    n_samples, n_features = feature_matrix.shape
    if n_features == 2380:
        resampled_matrix = feature_matrix
    else:
        logger.info(f"Resampling spectral features from {n_features} to 2,380 using 1D interpolation.")
        resampled_rows = []
        for i in range(n_samples):
            row = feature_matrix[i, :]
            f_interp = interp1d(
                incoming_wavelengths, 
                row, 
                kind='linear', 
                fill_value="extrapolate"
            )
            resampled_rows.append(f_interp(EXPECTED_WAVELENGTHS))
        resampled_matrix = np.array(resampled_rows)

    return resampled_matrix.tolist()


class SoilAnalysisViewSet(mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return SoilAnalysisJobListSerializer
        return SoilAnalysisJobSerializer

    def get_queryset(self):
        org = get_request_organization(self.request)
        if not org:
            return SoilAnalysisJob.objects.none()
        queryset = SoilAnalysisJob.objects.filter(organization=org).order_by('-created_at')

        # Defer massive fields during list views to keep queries extremely fast and memory-light
        if self.action == 'list':
            queryset = queryset.defer('spectra')

        return queryset

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

        # 2. Validate request serializer structure
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 3. Clean, Resample & Standardize Spectral Data Pipeline
        spectra_file = request.FILES.get('spectra_file')
        try:
            standardized_spectra = process_and_standardize_spectra(
                request.data, 
                spectra_file=spectra_file
            )
        except Exception as e:
            logger.error(f"Data processing error: {e}")
            return Response({"detail": f"Failed to process spectral data: {str(e)}"}, status=400)

        # 4. Save Job with organization and requested_by context
        job = serializer.save(
            organization=org,
            requested_by=request.user,
            spectra=standardized_spectra,
            status=SoilAnalysisJob.Status.PENDING
        )

        # 5. Offload to Celery Task
        logger.info(f"Enqueueing Job {job.id} with {len(standardized_spectra)} sample(s) to Celery...")
        analyze_soil_spectra.delay(job.id)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DashboardAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Dashboard Analytics",
        description="Returns aggregated soil statistics for the organization's dashboard.",
        responses={
            200: inline_serializer(
                name='DashboardAnalyticsResponse',
                fields={
                    'total_samples_all_time': serializers.IntegerField(),
                    'total_samples_this_month': serializers.IntegerField(),
                    'average_som': serializers.FloatField(),
                    'jobs_by_status': serializers.ListField(child=serializers.DictField()),
                }
            )
        }
    )
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