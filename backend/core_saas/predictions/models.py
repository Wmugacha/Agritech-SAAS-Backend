import uuid
import logging
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from organizations.models import Organization

logger = logging.getLogger(__name__)

class SoilAnalysisJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        RUNNING = 'RUNNING', _('Running')
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Ownership
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='analysis_jobs')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    
    # Scientific Data
    spectra = models.JSONField(help_text="Array of spectral absorbance values")
    
    # The output from the ML model
    predicted_properties = models.JSONField(null=True, blank=True)
    
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job {self.id} - {self.status}"