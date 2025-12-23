from django.test import TestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization
from .models import Subscription

User = get_user_model()

class SubscriptionSignalTest(TestCase):
    def test_default_subscription_created(self):
        """
        Test that creating an Organization automatically creates a FREE subscription.
        """
        org = Organization.objects.create(name="Signal Test Farm")
        
        # Reload from DB to ensure relationships are set
        org.refresh_from_db()
        
        self.assertTrue(hasattr(org, 'subscription'))
        self.assertEqual(org.subscription.plan, Subscription.PlanType.FREE)
        self.assertEqual(org.subscription.status, Subscription.Status.ACTIVE)
        
        # Check our hardcoded limits property
        self.assertEqual(org.subscription.limits['predictions'], 10)