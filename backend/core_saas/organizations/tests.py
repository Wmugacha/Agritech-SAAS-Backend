from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
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


class RBACTest(APITestCase):
    def setUp(self):
        # 1. Create an Organization
        self.org = Organization.objects.create(name="Test Farm")

        # 2. Create the Users
        self.admin_user = User.objects.create_user(email="admin@farm.com", password="pass")
        self.agronomist_user = User.objects.create_user(email="agro@farm.com", password="pass")
        self.viewer_user = User.objects.create_user(email="view@farm.com", password="pass")

        # 3. Assign Roles via Membership
        Membership.objects.create(
            user=self.admin_user, 
            organization=self.org, 
            role=Membership.ORG_ADMIN
        )
        Membership.objects.create(
            user=self.agronomist_user, 
            organization=self.org, 
            role=Membership.AGRONOMIST
        )
        Membership.objects.create(
            user=self.viewer_user, 
            organization=self.org, 
            role=Membership.VIEWER
        )

    def test_viewer_cannot_create(self):
        self.client.force_authenticate(user=self.viewer_user)
        response = self.client.post("/api/demo-create/", {})
        self.assertEqual(response.status_code, 403)

    def test_agronomist_can_create(self):
        self.client.force_authenticate(user=self.agronomist_user)
        response = self.client.post("/api/demo-create/", {})
        self.assertNotEqual(response.status_code, 403)

    def test_admin_has_full_access(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put("/api/demo-create/", {})
        self.assertNotEqual(response.status_code, 403)