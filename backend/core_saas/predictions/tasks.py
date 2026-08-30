import logging
import joblib
import os
import numpy as np
from django.conf import settings
from celery import shared_task
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

# Model Loading
CURRENT_MODEL_VERSION = "v1.0.0"  # Change to environment variable in production
MODEL_PATH = os.path.join(settings.BASE_DIR, 'predictions/ml_models/soil_model.pkl')
try:
    logger.info(f"Loading ML Model from: {MODEL_PATH}")
    metrics_model = joblib.load(MODEL_PATH)
    logger.info("ML Model loaded successfully.")
except Exception as e:
    logger.error(f"Could not load ML model: {e}")
    metrics_model = None


@shared_task
def analyze_soil_spectra(job_id):
    """
    ML Inference Task for Soil Organic Matter (SOM) predictions.
    Supports batch processing (single or multiple sample rows).
    """
    logger.info(f"Starting Analysis Task for Job {job_id}..........")
    
    try:
        if metrics_model is None:
            raise Exception("ML Model is not loaded on the worker.")

        # 1. Fetch Job
        job = SoilAnalysisJob.objects.get(id=job_id)
        job.status = SoilAnalysisJob.Status.RUNNING
        job.save()

        # 2. Extract & Convert Payload to 2D NumPy Array
        spectra_payload = job.spectra

        if spectra_payload is None:
            raise ValueError("No spectral data found in job record.")

        features_matrix = np.array(spectra_payload, dtype=float)

        # Reshape to 2D if single sample (1D list) was provided
        if features_matrix.ndim == 1:
            features_matrix = features_matrix.reshape(1, -1)

        # 3. Validation: Validate COLUMN dimension (shape[1]), supporting batch row inputs
        expected_features = getattr(metrics_model, 'n_features_in_', 2380)
        n_samples, n_features = features_matrix.shape

        if n_features != expected_features:
            raise ValueError(
                f"Shape mismatch: Model '{CURRENT_MODEL_VERSION}' expects {expected_features} columns/features, "
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
        job.model_version = CURRENT_MODEL_VERSION
        job.status = SoilAnalysisJob.Status.SUCCESS
        job.save()
        
    except SoilAnalysisJob.DoesNotExist:
        logger.error(f"❌ Job {job_id} not found!")
    
    except Exception as e:
        logger.exception(f"❌ Prediction Failed for Job {job_id}")
        if 'job' in locals():
            job.status = SoilAnalysisJob.Status.FAILED
            job.error_message = str(e)
            job.is_billable = False
            job.save()