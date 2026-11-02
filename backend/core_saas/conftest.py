"""Shared pytest fixtures for API tests.

Every test talks to the API through DRF's APIClient, so requests go
through the same URLs, serializers and permissions as real traffic.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from organizations.models import Membership, Organization

PASSWORD = "S3cure-test-pass!"


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def org(db):
    # The post_save signal attaches a FREE subscription automatically.
    return Organization.objects.create(name="Green Valley Co-op")


@pytest.fixture
def other_org(db):
    return Organization.objects.create(name="Rival Farms Ltd")


@pytest.fixture
def make_member(db):
    """Create a user with a role in an organization: make_member(org, "VIEWER")."""
    counter = {"n": 0}

    def _make(organization, role=Membership.OWNER, email=None):
        counter["n"] += 1
        email = email or f"{role.lower()}{counter['n']}@example.com"
        user = get_user_model().objects.create_user(email=email, password=PASSWORD)
        Membership.objects.create(user=user, organization=organization, role=role)
        return user

    return _make


@pytest.fixture
def owner(org, make_member):
    return make_member(org, Membership.OWNER)


@pytest.fixture
def client_for(api_client):
    """Return an APIClient authenticated as the given user."""

    def _client(user):
        api_client.force_authenticate(user=user)
        return api_client

    return _client
