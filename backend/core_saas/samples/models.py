import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from organizations.models import Organization

class SoilSample(models.Model):
    """
    Represents a single soil sample within a specific organization (tenant).
    Includes geolocation, agronomic context, and core soil metrics.
    """

    # --- Identity ---
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # --- Tenant & Traceability ---
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="soil_samples"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_soil_samples"
    )

    # --- Geolocation ---
    label = models.CharField(
        max_length=255, 
        help_text="User-defined name for the sample location (e.g. 'Field A - North')"
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # --- Agronomic Context ---
    depth_cm = models.PositiveIntegerField(
        default=15, 
        help_text="The depth at which the sample was taken"
    )
    crop_type = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Current or planned crop"
    )

    # --- Soil Metrics (NPK + pH) ---
    ph = models.FloatField(help_text="Soil acidity/alkalinity")
    nitrogen = models.FloatField(null=True, blank=True, help_text="mg/kg or ppm")
    phosphorus = models.FloatField(null=True, blank=True, help_text="mg/kg or ppm")
    potassium = models.FloatField(null=True, blank=True, help_text="mg/kg or ppm")

    # --- Metadata & System Fields ---
    metadata = models.JSONField(
        blank=True, 
        default=dict, 
        help_text="Extra data like lab IDs or sensor brand"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"{self.label} - {self.organization.name} ({self.created_at.date()})"

    def clean(self):
        """
        Custom validation to ensure the uploader belongs to the organization.
        """
        if self.uploaded_by and self.organization:
            from organizations.models import Membership
            exists = Membership.objects.filter(
                user=self.uploaded_by, 
                organization=self.organization
            ).exists()
            if not exists:
                raise ValidationError("The uploader must be a member of the assigned organization.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Triggers the clean() method before saving
        super().save(*args, **kwargs)