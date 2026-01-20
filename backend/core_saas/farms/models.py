import uuid
from django.db import models
from organizations.models import Organization
from django.conf import settings

class Farm(models.Model):
    """
    Represents a physical location or estate.
    Example: 'Green Valley Farm, Nakuru'
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='farms')

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='owned_farms',
        help_text="The user who owns/manages this specific farm"
    )
    
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, help_text="General location or address")
    total_area_hectares = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class Field(models.Model):
    """
    Represents a specific plot of land within a farm.
    Example: 'Block A - Maize'
    """
    class CropType(models.TextChoices):
        MAIZE = 'MAIZE', 'Maize'
        BEANS = 'BEANS', 'Beans'
        WHEAT = 'WHEAT', 'Wheat'
        COFFEE = 'COFFEE', 'Coffee'
        TEA = 'TEA', 'Tea'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='fields')
    
    name = models.CharField(max_length=255)
    crop_type = models.CharField(max_length=20, choices=CropType.choices, default=CropType.MAIZE)
    area_hectares = models.DecimalField(max_digits=10, decimal_places=2, help_text="Size of this specific field")
    
    # Simple Geo-location (Center point) - We can upgrade to Polygon later
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.crop_type}"