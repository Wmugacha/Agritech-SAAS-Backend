import pytest
from rest_framework import status
from model_bakery import baker
from django.contrib.auth import get_user_model
from organizations.models import Membership, Organization
from farms.models import Farm, Field

# --- FIXTURES (Setup Code) ---
@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def user_factory(db):
    """Helper to create users quickly"""
    def create_user(email="test@example.com"):
        User = get_user_model()
        return baker.make(User, email=email)
    return create_user

@pytest.fixture
def org_setup(user_factory):
    """Creates an Org and an Owner ready for testing"""
    owner = user_factory(email="owner@farm.com")
    org = baker.make(Organization, name="Test Org")
    
    # FIX: Use string 'OWNER' instead of Membership.OWNER
    baker.make(Membership, user=owner, organization=org, role='OWNER')
    
    return {
        'owner': owner,
        'org': org
    }

# --- TESTS ---

@pytest.mark.django_db
class TestFarmEndpoints:
    
    def test_create_farm_success(self, api_client, org_setup):
        """Test that an authenticated user can create a farm."""
        user = org_setup['owner']
        api_client.force_authenticate(user=user)
        
        payload = {
            "name": "Highland Estate",
            "location": "Nairobi",
            "total_area_hectares": 100.50
        }
        
        response = api_client.post('/api/agronomy/farms/', payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == "Highland Estate"
        
        # Verify DB links
        farm = Farm.objects.get(id=response.data['id'])
        assert farm.organization == org_setup['org']
        assert farm.owner == user

    def test_farm_isolation(self, api_client, org_setup, user_factory):
        """Test that users cannot see farms from other organizations."""
        # 1. Setup Farm in Org A
        farm_a = baker.make(Farm, organization=org_setup['org'], name="Org A Farm")
        
        # 2. Setup User in Org B (Different Company)
        user_b = user_factory(email="b@other.com")
        org_b = baker.make(Organization, name="Org B")
        # FIX: Use string 'OWNER'
        baker.make(Membership, user=user_b, organization=org_b, role='OWNER')
        
        # 3. User B tries to list farms
        api_client.force_authenticate(user=user_b)
        response = api_client.get('/api/agronomy/farms/')
        
        # 4. Should see 0 farms (Safety Check)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_farmer_visibility_restriction(self, api_client, org_setup, user_factory):
        """
        Test that a generic 'VIEWER' (Farmer) can only see farms they own,
        while an ADMIN can see everything.
        """
        org = org_setup['org']
        
        # 1. Setup Users
        admin_user = org_setup['owner'] # Already OWNER
        
        farmer_user = user_factory(email="farmer@farm.com")
        # FIX: Use string 'VIEWER' instead of Membership.VIEWER
        baker.make(Membership, user=farmer_user, organization=org, role='VIEWER')
        
        # 2. Setup Farms
        # Farm 1 owned by Farmer
        farm_own = baker.make(Farm, organization=org, owner=farmer_user, name="My Farm")
        # Farm 2 owned by Admin
        farm_other = baker.make(Farm, organization=org, owner=admin_user, name="Other Farm")
        
        # 3. Test Farmer View (Should see only 1)
        api_client.force_authenticate(user=farmer_user)
        resp = api_client.get('/api/agronomy/farms/')
        assert len(resp.data) == 1
        assert resp.data[0]['name'] == "My Farm"
        
        # 4. Test Admin View (Should see 2)
        api_client.force_authenticate(user=admin_user)
        resp = api_client.get('/api/agronomy/farms/')
        assert len(resp.data) == 2


@pytest.mark.django_db
class TestFieldEndpoints:
    
    def test_create_field_success(self, api_client, org_setup):
        """Test adding a field to a farm works normally for owners."""
        user = org_setup['owner']
        farm = baker.make(Farm, organization=org_setup['org'], owner=user)
        
        api_client.force_authenticate(user=user)
        
        payload = {
            "farm": farm.id,
            "name": "Block A",
            "crop_type": "MAIZE",
            "area_hectares": 10.0
        }
        
        response = api_client.post('/api/agronomy/fields/', payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Field.objects.count() == 1
        assert Field.objects.first().farm == farm

    def test_create_field_security_check(self, api_client, org_setup, user_factory):
        """
        Test that a generic user cannot create a field on a farm they don't own.
        """
        org = org_setup['org']
        
        # 1. Setup two users in the SAME org
        # User A (Owner of the farm)
        user_a = org_setup['owner']
        farm_a = baker.make(Farm, organization=org, owner=user_a)
        
        # User B (Just a viewer/farmer, NOT the owner of this farm)
        user_b = user_factory(email="thief@farm.com")
        # FIX: Use string 'VIEWER'
        baker.make(Membership, user=user_b, organization=org, role='VIEWER')
        
        # 2. User B tries to add a field to User A's farm
        api_client.force_authenticate(user=user_b)
        
        payload = {
            "farm": farm_a.id,
            "name": "Malicious Field",
            "crop_type": "MAIZE",
            "area_hectares": 5.0
        }
        
        response = api_client.post('/api/agronomy/fields/', payload)
        
        # 3. Should be Forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN