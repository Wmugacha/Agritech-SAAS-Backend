from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization, Membership
from .models import SoilSample

User = get_user_model()


class SoilSampleAPITest(APITestCase):

    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")

        self.agronomist = User.objects.create_user(
            email="agro@test.com", password="pass"
        )
        self.viewer = User.objects.create_user(
            email="viewer@test.com", password="pass"
        )

        Membership.objects.create(
            user=self.agronomist,
            organization=self.org_a,
            role=Membership.AGRONOMIST
        )

        Membership.objects.create(
            user=self.viewer,
            organization=self.org_a,
            role=Membership.VIEWER
        )

    def test_agronomist_can_create_soil_sample(self):
        self.client.force_authenticate(self.agronomist)

        payload = {
            "label": "Field A - North",
            "ph": 6.4,
            "latitude": -1.2921,
            "longitude": 36.8219,
            "depth_cm": 15,
            "crop_type": "Maize",
        }

        response = self.client.post("/api/soil-samples/", payload)
        self.assertEqual(response.status_code, 201)

    def test_viewer_cannot_create_soil_sample(self):
        self.client.force_authenticate(self.viewer)

        payload = {
            "label": "Field B",
            "ph": 5.9
        }

        response = self.client.post("/api/soil-samples/", payload)
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_see_other_org_samples(self):
        SoilSample.objects.create(
            organization=self.org_b,
            uploaded_by=None,
            label="Hidden Sample",
            ph=7.0
        )

        self.client.force_authenticate(self.agronomist)
        response = self.client.get("/api/soil-samples/")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data), 0)
