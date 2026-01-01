import time
import logging
import random
import statistics
from celery import shared_task
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

@shared_task
def analyze_soil_spectra(job_id):
    """
    Background task to process spectral data.
    Simulates loading a PLS model and predicting a property.
    """
    logger.info(f"🚀 Starting Analysis Task for Job {job_id}")
    
    try:
        # 1. Fetch Job
        job = SoilAnalysisJob.objects.get(id=job_id)
        job.status = SoilAnalysisJob.Status.RUNNING
        job.save()

        # 2. Simulate Model Loading (Heavy I/O)
        time.sleep(3) 
        
        # 3. Simulate The "Science"
        # In Day 8, we will load the real .pkl file here.
        # For now, we create a 'dummy' prediction based on the input data 
        # so we can prove the data actually flowed through.
        spectra = job.spectra
        
        # Dummy Logic: Calculate mean absorbance as a proxy for SOM
        # (This is just to prove the worker read the JSON correctly)
        mean_absorbance = statistics.mean(spectra)
        
        # Add some random noise to simulate model variance
        predicted_som = (mean_absorbance * 10) + random.uniform(-0.1, 0.1)
        
        logger.info(f"🧪 Prediction complete for Job {job_id}. Calc SOM: {predicted_som}")

        # 4. Save Results
        job.predicted_properties = {
            "SOM": round(predicted_som, 3),
            "Confidence": "High" if len(spectra) > 100 else "Low"
        }
        job.status = SoilAnalysisJob.Status.SUCCESS
        job.save()
        
    except SoilAnalysisJob.DoesNotExist:
        logger.error(f"❌ Job {job_id} not found!")
    except Exception as e:
        logger.exception(f"❌ Prediction Failed for Job {job_id}")
        # Graceful Failure
        if 'job' in locals():
            job.status = SoilAnalysisJob.Status.FAILED
            job.error_message = str(e)
            job.save()