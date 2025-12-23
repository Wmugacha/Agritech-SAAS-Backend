import uuid
import logging
from django.db import models
from django.utils.translation import gettext_lazy as _
from organizations.models import Organization

logger = logging.getLogger(__name__)

class Subscription(models.Model):
    """
    Represents the billing state of an Organization.
    Decoupled from payment providers (Stripe) for system resilience.
    """
    class PlanType(models.TextChoices):
        FREE = 'FREE', _('Free Tier')
        PRO = 'PRO', _('Professional Tier')

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        INACTIVE = 'INACTIVE', _('Inactive')
        PAST_DUE = 'PAST_DUE', _('Past Due')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # One subscription per organization
    organization = models.OneToOneField(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    
    plan = models.CharField(
        max_length=20, 
        choices=PlanType.choices, 
        default=PlanType.FREE,
        db_index=True
    )
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.ACTIVE,
        db_index=True
    )

    # To be used later for billing cycles
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} - {self.plan}"

    # Prediction Limits - To be adjusted later
    @property
    def limits(self):
        if self.plan == self.PlanType.PRO:
            return {"predictions": 1000, "storage_mb": 1000}
        return {"predictions": 10, "storage_mb": 100}