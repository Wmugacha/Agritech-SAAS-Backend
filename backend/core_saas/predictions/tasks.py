import logging
import joblib
import os
import numpy as np
from django.conf import settings
from celery import shared_task
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

# Model Loading
CURRENT_MODEL_VERSION = "v1.0.0" # Change to enviroment variable in production
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
    ML Inference Task.
    Uses Pre-trained PLS Model to predict SOM.
    """
    logger.info(f"Starting Analysis Task for Job {job_id}..........")
    
    try:
        if metrics_model is None:
            raise Exception("ML Model is not loaded on the worker.")

        # 1. Fetch Job
        job = SoilAnalysisJob.objects.get(id=job_id)
        job.status = SoilAnalysisJob.Status.RUNNING
        job.save()

        # --- TIER 2 VALIDATION: SCIENTIFIC CHECKS ---
        spectra_list = job.spectra
        
        # Dynamically ask the loaded model what shape it expects!
        if hasattr(metrics_model, 'n_features_in_'):
            expected_features = metrics_model.n_features_in_
            if len(spectra_list) != expected_features:
                raise ValueError(
                    f"Shape mismatch: Model '{CURRENT_MODEL_VERSION}' expects {expected_features} features, "
                    f"but received {len(spectra_list)}."
                )

        # 2. Prepare Data (Inference)
        # Convert the list to a numpy array and reshape it
        spectra_array = np.array(job.spectra).reshape(1, -1)
        
        # 3. Predict
        prediction = metrics_model.predict(spectra_array)
        
        predicted_som = float(prediction.flatten()[0])
        #predicted_som = float(prediction[0][0])
        
        logger.info(f"🧪 Prediction complete. SOM: {predicted_som}")

        # 4. Save Results
        job.predicted_properties = {
            "SOM": round(predicted_som, 3),
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