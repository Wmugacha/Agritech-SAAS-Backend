import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from organizations.models import Organization
from .models import Subscription

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Organization)
def create_default_subscription(sender, instance, created, **kwargs):
    """
    Automatically attach a FREE subscription to every new Organization.
    """
    if created:
        try:
            Subscription.objects.create(
                organization=instance,
                plan=Subscription.PlanType.FREE,
                status=Subscription.Status.ACTIVE
            )
            logger.info(f"✅ Subscription created for Org: {instance.name} (ID: {instance.id})")
        except Exception as e:
            logger.error(f"❌ Failed to create subscription for Org {instance.name}: {e}")