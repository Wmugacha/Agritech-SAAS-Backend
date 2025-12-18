from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Organization, Membership

User = get_user_model()

class TenantIsolationTest(TestCase):

    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")

        self.user_a = User.objects.create_user(
            email="a@test.com",
            password="password123"
        )

        self.user_b = User.objects.create_user(
            email="b@test.com",
            password="password123"
        )

        Membership.objects.create(
            user=self.user_a,
            organization=self.org_a
        )

        Membership.objects.create(
            user=self.user_b,
            organization=self.org_b
        )

    def test_users_belong_to_separate_orgs(self):
        self.assertNotEqual(
            self.user_a.memberships.first().organization,
            self.user_b.memberships.first().organization
        )
