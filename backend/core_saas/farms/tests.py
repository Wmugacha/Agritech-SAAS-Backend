import pytest

from farms.models import CropSeason, Farm, FarmActivity, Field
from organizations.models import Membership

FARMS_URL = "/api/agronomy/farms/"
FIELDS_URL = "/api/agronomy/fields/"
SEASONS_URL = "/api/agronomy/seasons/"
ACTIVITIES_URL = "/api/agronomy/activities/"

pytestmark = pytest.mark.django_db


def ids(response):
    """The API is paginated, so the items live under "results"."""
    return {item["id"] for item in response.data["results"]}


@pytest.fixture
def farm(org, owner):
    return Farm.objects.create(organization=org, owner=owner, name="Rift Valley Estate", location="Nakuru")


@pytest.fixture
def field(farm):
    return Field.objects.create(farm=farm, name="Block A", crop_type="MAIZE", area_hectares=12.5)


class TestFarms:
    def test_requires_auth(self, api_client):
        assert api_client.get(FARMS_URL).status_code == 401

    def test_create_farm_sets_org_and_owner_from_request(self, client_for, org, owner, other_org):
        payload = {
            "name": "Highland Estate",
            "location": "Nairobi",
            "total_area_hectares": "100.50",
            # Clients must not be able to pick another tenant
            "organization": str(other_org.id),
        }

        response = client_for(owner).post(FARMS_URL, payload, format="json")

        assert response.status_code == 201
        farm = Farm.objects.get(id=response.data["id"])
        assert farm.organization == org
        assert farm.owner == owner

    def test_list_is_paginated(self, client_for, owner, farm):
        response = client_for(owner).get(FARMS_URL)

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert ids(response) == {str(farm.id)}

    def test_user_cannot_see_other_org_farms(self, client_for, farm, other_org, make_member):
        outsider = make_member(other_org, Membership.OWNER)

        response = client_for(outsider).get(FARMS_URL)

        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_user_cannot_open_other_org_farm_by_id(self, client_for, farm, other_org, make_member):
        outsider = make_member(other_org, Membership.OWNER)

        response = client_for(outsider).get(f"{FARMS_URL}{farm.id}/")

        assert response.status_code == 404

    def test_viewer_sees_only_own_farms_admin_sees_all(self, client_for, org, owner, farm, make_member):
        viewer = make_member(org, Membership.VIEWER)
        own_farm = Farm.objects.create(organization=org, owner=viewer, name="My Farm", location="Eldoret")

        assert ids(client_for(viewer).get(FARMS_URL)) == {str(own_farm.id)}
        assert ids(client_for(owner).get(FARMS_URL)) == {str(own_farm.id), str(farm.id)}

    def test_agronomist_sees_all_org_farms(self, client_for, org, farm, make_member):
        agronomist = make_member(org, Membership.AGRONOMIST)

        assert ids(client_for(agronomist).get(FARMS_URL)) == {str(farm.id)}


class TestFields:
    def payload(self, farm, **overrides):
        return {"farm": str(farm.id), "name": "Block B", "crop_type": "BEANS", "area_hectares": "4.00", **overrides}

    def test_owner_can_add_field_to_farm(self, client_for, owner, farm):
        response = client_for(owner).post(FIELDS_URL, self.payload(farm), format="json")

        assert response.status_code == 201
        assert Field.objects.get(id=response.data["id"]).farm == farm

    def test_viewer_cannot_add_field_to_someone_elses_farm(self, client_for, org, farm, make_member):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).post(FIELDS_URL, self.payload(farm), format="json")

        assert response.status_code == 403
        assert not Field.objects.exists()

    def test_cannot_add_field_to_farm_in_other_org(self, client_for, farm, other_org, make_member):
        outsider = make_member(other_org, Membership.OWNER)

        response = client_for(outsider).post(FIELDS_URL, self.payload(farm), format="json")

        # Same error as a farm id that doesn't exist, so the other tenant's farm isn't revealed
        assert response.status_code == 400
        assert "farm" in response.data
        assert not Field.objects.exists()

    def test_invalid_crop_type_is_rejected(self, client_for, owner, farm):
        response = client_for(owner).post(FIELDS_URL, self.payload(farm, crop_type="BANANA"), format="json")

        assert response.status_code == 400
        assert "crop_type" in response.data


class TestCropTimeline:
    """Replaces the old day 14 script: field -> season -> activity -> nested timeline."""

    def test_season_and_activity_show_up_in_timeline(self, client_for, owner, field):
        client = client_for(owner)

        season = client.post(
            SEASONS_URL,
            {
                "field": field.id,
                "crop_type": "MAIZE",
                "season_name": "Long Rains 2026",
                "status": "GROWING",
                "planting_date": "2026-03-01",
                "target_yield_kg": "4500.00",
            },
            format="json",
        )
        assert season.status_code == 201

        activity = client.post(
            ACTIVITIES_URL,
            {
                "season": season.data["id"],
                "activity_type": "FERTILIZER",
                "activity_date": "2026-03-15",
                "description": "DAP top dressing",
                "cost": "3500.00",
            },
            format="json",
        )
        assert activity.status_code == 201

        timeline = client.get(f"{SEASONS_URL}{season.data['id']}/")
        assert timeline.status_code == 200
        assert [a["activity_type"] for a in timeline.data["activities"]] == ["FERTILIZER"]

    def test_viewer_cannot_add_season_to_someone_elses_field(self, client_for, org, field, make_member):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).post(
            SEASONS_URL, {"field": field.id, "season_name": "Short Rains 2026"}, format="json"
        )

        assert response.status_code == 403
        assert not CropSeason.objects.exists()

    def test_viewer_cannot_log_activity_on_someone_elses_season(self, client_for, org, field, make_member):
        season = CropSeason.objects.create(field=field, season_name="Long Rains 2026")
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).post(
            ACTIVITIES_URL,
            {"season": season.id, "activity_type": "WEEDING", "activity_date": "2026-04-01"},
            format="json",
        )

        assert response.status_code == 403
        assert not FarmActivity.objects.exists()


class TestRolePermissions:
    """Reads need any role, writes need AGRONOMIST or above, deletes need OWNER or ORG_ADMIN."""

    def test_viewer_cannot_create_farm(self, client_for, org, make_member):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).post(FARMS_URL, {"name": "Sneaky Farm", "location": "Kisumu"}, format="json")

        assert response.status_code == 403
        assert not Farm.objects.exists()

    def test_viewer_can_still_list_farms(self, client_for, org, make_member):
        viewer = make_member(org, Membership.VIEWER)

        assert client_for(viewer).get(FARMS_URL).status_code == 200

    def test_agronomist_can_create_farm(self, client_for, org, make_member):
        agronomist = make_member(org, Membership.AGRONOMIST)

        response = client_for(agronomist).post(FARMS_URL, {"name": "Trial Plot", "location": "Kisii"}, format="json")

        assert response.status_code == 201

    def test_viewer_cannot_edit_farm(self, client_for, org, farm, make_member):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).patch(f"{FARMS_URL}{farm.id}/", {"name": "Renamed"}, format="json")

        assert response.status_code == 403

    def test_agronomist_cannot_delete_farm(self, client_for, org, farm, make_member):
        agronomist = make_member(org, Membership.AGRONOMIST)

        response = client_for(agronomist).delete(f"{FARMS_URL}{farm.id}/")

        assert response.status_code == 403
        assert Farm.objects.filter(id=farm.id).exists()

    def test_owner_can_delete_farm(self, client_for, owner, farm):
        response = client_for(owner).delete(f"{FARMS_URL}{farm.id}/")

        assert response.status_code == 204
        assert not Farm.objects.filter(id=farm.id).exists()

    def test_user_without_org_is_forbidden(self, client_for, django_user_model):
        loner = django_user_model.objects.create_user(email="loner@example.com", password="x")

        assert client_for(loner).get(FARMS_URL).status_code == 403

    @pytest.mark.parametrize("url", [FIELDS_URL, SEASONS_URL, ACTIVITIES_URL])
    def test_viewer_cannot_create_on_any_agronomy_endpoint(self, client_for, org, make_member, url):
        viewer = make_member(org, Membership.VIEWER)

        assert client_for(viewer).post(url, {}, format="json").status_code == 403


@pytest.fixture
def their_field(other_org):
    """A farm, field and season that belong to another organization."""
    farm = Farm.objects.create(organization=other_org, name="Their Farm", location="Thika")
    return Field.objects.create(farm=farm, name="Their Block", crop_type="TEA", area_hectares=3)


class TestCrossOrgForeignKeys:
    """Every foreign key in a request body must point at our own organization, on create AND update."""

    def test_field_cannot_be_moved_to_other_org_farm(self, client_for, owner, field, their_field):
        response = client_for(owner).patch(
            f"{FIELDS_URL}{field.id}/", {"farm": str(their_field.farm.id)}, format="json"
        )

        assert response.status_code == 400
        assert "farm" in response.data
        field.refresh_from_db()
        assert field.farm.organization == owner.memberships.get().organization

    def test_season_cannot_be_created_on_other_org_field(self, client_for, owner, their_field):
        response = client_for(owner).post(
            SEASONS_URL, {"field": their_field.id, "season_name": "Long Rains 2026"}, format="json"
        )

        assert response.status_code == 400
        assert "field" in response.data
        assert not CropSeason.objects.exists()

    def test_season_cannot_be_moved_to_other_org_field(self, client_for, owner, field, their_field):
        season = CropSeason.objects.create(field=field, season_name="Long Rains 2026")

        response = client_for(owner).patch(f"{SEASONS_URL}{season.id}/", {"field": their_field.id}, format="json")

        assert response.status_code == 400
        season.refresh_from_db()
        assert season.field == field

    def test_activity_cannot_be_created_on_other_org_season(self, client_for, owner, their_field):
        their_season = CropSeason.objects.create(field=their_field, season_name="Short Rains 2026")

        response = client_for(owner).post(
            ACTIVITIES_URL,
            {"season": their_season.id, "activity_type": "WEEDING", "activity_date": "2026-04-01"},
            format="json",
        )

        assert response.status_code == 400
        assert "season" in response.data
        assert not FarmActivity.objects.exists()

    def test_activity_cannot_be_moved_to_other_org_season(self, client_for, owner, field, their_field):
        season = CropSeason.objects.create(field=field, season_name="Long Rains 2026")
        their_season = CropSeason.objects.create(field=their_field, season_name="Short Rains 2026")
        activity = FarmActivity.objects.create(season=season, activity_type="WEEDING", activity_date="2026-04-01")

        response = client_for(owner).patch(
            f"{ACTIVITIES_URL}{activity.id}/", {"season": their_season.id}, format="json"
        )

        assert response.status_code == 400
        activity.refresh_from_db()
        assert activity.season == season

    def test_farm_can_be_assigned_to_a_member(self, client_for, org, owner, make_member):
        farmer = make_member(org, Membership.VIEWER)

        response = client_for(owner).post(
            FARMS_URL, {"name": "Farmer's Plot", "location": "Nyeri", "owner": str(farmer.id)}, format="json"
        )

        assert response.status_code == 201
        assert Farm.objects.get(id=response.data["id"]).owner == farmer
        # ...and the farmer can now see it
        assert ids(client_for(farmer).get(FARMS_URL)) == {response.data["id"]}

    def test_farm_cannot_be_assigned_to_outsider(self, client_for, owner, other_org, make_member):
        outsider = make_member(other_org, Membership.OWNER)

        response = client_for(owner).post(
            FARMS_URL, {"name": "Gift", "location": "Nyeri", "owner": str(outsider.id)}, format="json"
        )

        assert response.status_code == 400
        assert "owner" in response.data