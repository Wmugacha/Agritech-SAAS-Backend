import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APITestCase

from .middleware import OrganizationMiddleware
from .models import Membership, Organization

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
        response = self.client.post("/api/organizations/demo-create/", {})
        self.assertEqual(response.status_code, 403)

    def test_agronomist_can_create(self):
        self.client.force_authenticate(user=self.agronomist_user)
        # Manually verify the membership exists in the DB for the test
        response = self.client.post("/api/organizations/demo-create/", {})
    
        if response.status_code == 403:
            print(f"Debug 403: {response.data}")
            
        self.assertEqual(response.status_code, 201)

    def test_admin_has_full_access(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put("/api/organizations/demo-create/", {})
        self.assertEqual(response.status_code, 200)

# --- pytest-style tests for tenant resolution ---

CREATE_ORG_URL = "/api/organizations/create/"


@pytest.mark.django_db
def test_middleware_picks_oldest_org_for_multi_org_user(make_member, org, other_org):
    user = make_member(org, Membership.AGRONOMIST)
    Membership.objects.create(user=user, organization=other_org, role=Membership.OWNER)
    request = RequestFactory().get("/api/agronomy/farms/")
    request.user = user

    # Used to raise MultipleObjectsReturned, which surfaced as a 500
    OrganizationMiddleware(lambda req: req)(request)

    assert request.organization == org
    assert request.role == Membership.AGRONOMIST


@pytest.mark.django_db
def test_user_without_org_can_create_one(client_for, django_user_model):
    user = django_user_model.objects.create_user(email="founder@example.com", password="x")

    response = client_for(user).post(CREATE_ORG_URL, {"name": "Founders Co-op"}, format="json")

    assert response.status_code == 201
    membership = Membership.objects.get(user=user)
    assert membership.role == Membership.OWNER
    assert membership.organization.subscription.plan == "FREE"


@pytest.mark.django_db
def test_user_cannot_join_a_second_org_by_creating_one(client_for, owner):
    response = client_for(owner).post(CREATE_ORG_URL, {"name": "Second Co-op"}, format="json")

    assert response.status_code == 400
    assert Membership.objects.filter(user=owner).count() == 1
    assert not Organization.objects.filter(name="Second Co-op").exists()
