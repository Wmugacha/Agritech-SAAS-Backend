import logging

import joblib
import numpy as np
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import OperationalError

from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

# Model Loading
MODEL_PATH = settings.ML_MODEL_PATH
try:
    logger.info(f"Loading ML Model from: {MODEL_PATH}")
    metrics_model = joblib.load(MODEL_PATH)
    logger.info("ML Model loaded successfully.")
except Exception:
    logger.exception("Could not load ML model")
    metrics_model = None

MAX_RETRIES = 3

def mark_job_failed(job_id, message):
    """Mark a job FAILED and refund it. Uses update() so it works even if we never loaded the job."""
    SoilAnalysisJob.objects.filter(id=job_id).update(
        status=SoilAnalysisJob.Status.FAILED,
        error_message=message,
        is_billable=False,
    )


@shared_task(
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=settings.ML_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.ML_TASK_TIME_LIMIT,
)
def analyze_soil_spectra(self, job_id):
    """
    ML Inference Task for Soil Organic Matter (SOM) predictions.
    Supports batch processing (single or multiple sample rows).

    Failure handling:
    - Database errors are transient: retry with exponential backoff (2s, 4s, 8s), then fail the job.
    - Hitting the soft time limit fails the job instead of leaving it RUNNING.
    - Anything else (bad shape, missing model) is permanent: fail the job right away.
    Failed jobs are marked is_billable=False so they don't count against the quota.
    """

    logger.info(f"Starting Analysis Task for Job {job_id} (attempt {self.request.retries + 1})")
    
    try:
        # 1. Fetch Job
        job = SoilAnalysisJob.objects.get(id=job_id)
        job.status = SoilAnalysisJob.Status.RUNNING
        job.save()
        
        if metrics_model is None:
            raise RuntimeError("ML model is not loaded on the worker.")

        # 2. Extract & Convert Payload to 2D NumPy Array
        spectra_payload = job.spectra

        if spectra_payload is None:
            raise ValueError("No spectral data found in job record.")

        features_matrix = np.array(spectra_payload, dtype=float)

        # Reshape to 2D if single sample (1D list) was provided
        if features_matrix.ndim == 1:
            features_matrix = features_matrix.reshape(1, -1)

        # 3. Validation: Validate COLUMN dimension (shape[1]), supporting batch row inputs
        model_version = settings.ML_MODEL_VERSION
        expected_features = getattr(metrics_model, 'n_features_in_', 2380)
        n_samples, n_features = features_matrix.shape

        if n_features != expected_features:
            raise ValueError(
                f"Shape mismatch: Model '{model_version}' expects {expected_features} columns/features, "
                f"but received {n_features} columns across {n_samples} sample(s)."
            )

        # 4. Perform Model Inference
        predictions = metrics_model.predict(features_matrix)
        predictions_flat = predictions.flatten().tolist()

        logger.info(f"🧪 Inference complete across {n_samples} sample(s). SOM Predictions: {predictions_flat}")

        # 5. Format & Save Output (single float for single sample, list for batch)
        if len(predictions_flat) == 1:
            result_som = round(predictions_flat[0], 3)
        else:
            result_som = [round(val, 3) for val in predictions_flat]

        job.predicted_properties = {
            "SOM": result_som,
            "sample_count": n_samples,
            "Method": "PLSR_v1"
        }
        job.model_version = model_version
        job.status = SoilAnalysisJob.Status.SUCCESS
        job.save()
        
    except SoilAnalysisJob.DoesNotExist:
        logger.error(f"❌ Job {job_id} not found!")

    except OperationalError as exc:
        if self.request.retries < MAX_RETRIES:
            countdown = 2 ** (self.request.retries + 1)
            logger.warning(f"Database error on Job {job_id}, retrying in {countdown}s: {exc}")
            raise self.retry(exc=exc, countdown=countdown)
        logger.exception(f"❌ Job {job_id} failed after {MAX_RETRIES} retries")
        mark_job_failed(job_id, "Database unavailable, please resubmit.")

    except SoftTimeLimitExceeded:
        logger.error(f"❌ Job {job_id} hit the {settings.ML_TASK_SOFT_TIME_LIMIT}s time limit")
        mark_job_failed(job_id, "Prediction timed out.")

    
    except Exception as e:
        logger.exception(f"❌ Prediction Failed for Job {job_id}")
        mark_job_failed(job_id, str(e))
