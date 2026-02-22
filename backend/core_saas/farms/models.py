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


class CropSeason(models.Model):
    CROP_CHOICES = (
        ('MAIZE', 'Maize'),
        ('BEANS', 'Beans'),
        ('WHEAT', 'Wheat'),
        ('COFFEE', 'Coffee'),
        ('TEA', 'Tea'),
        ('OTHER', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('PLANNED', 'Planned'),
        ('GROWING', 'Growing'),
        ('HARVESTED', 'Harvested'),
        ('FAILED', 'Failed'),
    )

    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='seasons')
    crop_type = models.CharField(max_length=50, choices=CROP_CHOICES, default='MAIZE')
    season_name = models.CharField(max_length=100, help_text="e.g., Long Rains 2026")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    # Crop Timeline
    planting_date = models.DateField(null=True, blank=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    actual_harvest_date = models.DateField(null=True, blank=True)
    
    # Crop Season Results
    target_yield_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_yield_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.field.name} - {self.crop_type} ({self.season_name})"


class FarmActivity(models.Model):
    ACTIVITY_CHOICES = (
        ('SOIL_TEST', 'Soil Testing'),
        ('PLANTING', 'Planting'),
        ('FERTILIZER', 'Fertilizer Application'),
        ('WATER_CONSERVATION', 'Water & Soil Conservation'),
        ('WEEDING', 'Weeding / Herbicide'),
        ('HARVESTING', 'Harvesting'),
    )

    season = models.ForeignKey(CropSeason, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_CHOICES)
    activity_date = models.DateField()
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activity_date']
        verbose_name_plural = "Farm Activities"

    def __str__(self):
        return f"{self.get_activity_type_display()} on {self.activity_date}"