import logging
import joblib
import os
import numpy as np
from django.conf import settings
from celery import shared_task
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

# Model Loading
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
        job.status = SoilAnalysisJob.Status.SUCCESS
        job.save()
        
    except SoilAnalysisJob.DoesNotExist:
        logger.error(f"❌ Job {job_id} not found!")
    except Exception as e:
        logger.exception(f"❌ Prediction Failed for Job {job_id}")
        if 'job' in locals():
            job.status = SoilAnalysisJob.Status.FAILED
            job.error_message = str(e)
            job.save()