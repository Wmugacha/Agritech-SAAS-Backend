from unittest import mock

import numpy as np
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from farms.models import Farm, Field
from organizations.models import Membership
from predictions import tasks
from predictions.models import SoilAnalysisJob

PREDICT_URL = "/api/predict/"
DASHBOARD_URL = "/api/predict/analytics/dashboard/"
N_FEATURES = 2380

pytestmark = pytest.mark.django_db


@pytest.fixture
def enqueue():
    """Stop real Celery calls; tests assert on what would have been queued."""
    with mock.patch.object(tasks.analyze_soil_spectra, "delay") as delay:
        yield delay


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # Uploaded CSVs go to a temp dir instead of the repo's media/ folder
    settings.MEDIA_ROOT = tmp_path


class FakeModel:
    """Stands in for soil_model.pkl (gitignored, so not in CI)."""

    n_features_in_ = N_FEATURES

    def predict(self, X):
        return np.full((X.shape[0], 1), 2.5)


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(tasks, "metrics_model", FakeModel())


@pytest.fixture
def field(org, owner):
    farm = Farm.objects.create(organization=org, owner=owner, name="Analytics Farm", location="Nairobi")
    return Field.objects.create(farm=farm, name="Test Block A", crop_type="MAIZE", area_hectares=10)


def csv_upload(text):
    return SimpleUploadedFile("spectra.csv", text.encode(), content_type="text/csv")


class TestSubmitPrediction:
    def test_requires_auth(self, api_client):
        assert api_client.post(PREDICT_URL, {"spectra": [0.45] * N_FEATURES}, format="json").status_code == 401

    def test_user_without_org_is_blocked(self, client_for, django_user_model, enqueue):
        loner = django_user_model.objects.create_user(email="loner@example.com", password="x")

        response = client_for(loner).post(PREDICT_URL, {"spectra": [0.45] * N_FEATURES}, format="json")

        assert response.status_code == 403
        enqueue.assert_not_called()

    def test_valid_json_creates_pending_job_and_enqueues_it(self, client_for, org, owner, field, enqueue):
        response = client_for(owner).post(
            PREDICT_URL, {"field": str(field.id), "spectra": [0.45] * N_FEATURES}, format="json"
        )

        assert response.status_code == 201
        assert response.data["status"] == "PENDING"
        job = SoilAnalysisJob.objects.get(id=response.data["id"])
        assert job.organization == org
        assert job.requested_by == owner
        assert job.field == field
        enqueue.assert_called_once_with(job.id)

    def test_field_from_another_org_is_rejected(self, client_for, owner, other_org, enqueue):
        their_farm = Farm.objects.create(organization=other_org, name="Their Farm", location="Thika")
        their_field = Field.objects.create(farm=their_farm, name="Their Block", crop_type="TEA", area_hectares=3)

        response = client_for(owner).post(
            PREDICT_URL, {"field": str(their_field.id), "spectra": [0.45] * N_FEATURES}, format="json"
        )

        assert response.status_code == 400
        assert "field" in response.data
        assert not SoilAnalysisJob.objects.exists()
        enqueue.assert_not_called()

    def test_short_spectra_are_resampled_to_model_width(self, client_for, owner, enqueue):
        response = client_for(owner).post(PREDICT_URL, {"spectra": [0.1, 0.2, 0.3, 0.4]}, format="json")

        assert response.status_code == 201
        job = SoilAnalysisJob.objects.get(id=response.data["id"])
        assert np.array(job.spectra).shape == (1, N_FEATURES)

    @pytest.mark.parametrize(
        "payload",
        [{}, {"spectra": []}, {"spectra": ["garbage", "data"]}],
        ids=["missing", "empty", "strings"],
    )
    def test_bad_spectra_are_rejected(self, client_for, owner, enqueue, payload):
        response = client_for(owner).post(PREDICT_URL, payload, format="json")

        assert response.status_code == 400
        assert not SoilAnalysisJob.objects.exists()
        enqueue.assert_not_called()

    def test_csv_with_wavelength_header_is_accepted(self, client_for, owner, enqueue):
        wavelengths = np.linspace(3999.053, 600.0723, 50)
        header = ",".join(f"{w:.3f}" for w in wavelengths)  ",SOM"
        rows = "\n".join(",".join(["0.45"] * 50)  ",3.1" for _ in range(2))
        upload = csv_upload(f"{header}\n{rows}\n")

        response = client_for(owner).post(PREDICT_URL, {"spectra_file": upload}, format="multipart")

        assert response.status_code == 201
        job = SoilAnalysisJob.objects.get(id=response.data["id"])
        # SOM (the lab answer) is dropped and both rows are resampled
        assert np.array(job.spectra).shape == (2, N_FEATURES)

    def test_headerless_csv_keeps_its_only_row(self, client_for, owner, enqueue):
        # The old day 12 script wrote one row and no header
        upload = csv_upload(",".join(["0.45"] * N_FEATURES)  "\n")

        response = client_for(owner).post(PREDICT_URL, {"spectra_file": upload}, format="multipart")

        assert response.status_code == 201
        job = SoilAnalysisJob.objects.get(id=response.data["id"])
        assert np.array(job.spectra).shape == (1, N_FEATURES)


class TestRolePermissions:
    def test_viewer_cannot_submit_prediction(self, client_for, org, make_member, enqueue):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).post(PREDICT_URL, {"spectra": [0.45] * N_FEATURES}, format="json")

        assert response.status_code == 403
        assert not SoilAnalysisJob.objects.exists()
        enqueue.assert_not_called()

    def test_agronomist_can_submit_prediction(self, client_for, org, make_member, enqueue):
        agronomist = make_member(org, Membership.AGRONOMIST)

        response = client_for(agronomist).post(PREDICT_URL, {"spectra": [0.45] * N_FEATURES}, format="json")

        assert response.status_code == 201

    def test_viewer_can_list_jobs(self, client_for, org, make_member):
        viewer = make_member(org, Membership.VIEWER)

        assert client_for(viewer).get(PREDICT_URL).status_code == 200


class TestListAndRetrieve:
    def test_list_shows_only_my_org_jobs_without_raw_spectra(self, client_for, org, owner, other_org):
        mine = SoilAnalysisJob.objects.create(organization=org, spectra=[[0.1] * 3])
        SoilAnalysisJob.objects.create(organization=other_org, spectra=[[0.1] * 3])

        response = client_for(owner).get(PREDICT_URL)

        assert response.status_code == 200
        assert [job["id"] for job in response.data["results"]] == [str(mine.id)]
        assert "spectra" not in response.data["results"][0]

    def test_cannot_retrieve_other_org_job(self, client_for, owner, other_org):
        theirs = SoilAnalysisJob.objects.create(organization=other_org, spectra=[[0.1] * 3])

        assert client_for(owner).get(f"{PREDICT_URL}{theirs.id}/").status_code == 404


class TestAnalyzeTask:
    """Runs the Celery task body directly, with a fake model."""

    def make_job(self, org, spectra):
        return SoilAnalysisJob.objects.create(organization=org, spectra=spectra)

    def test_success_stores_prediction(self, org, fake_model):
        job = self.make_job(org, [[0.45] * N_FEATURES])

        tasks.analyze_soil_spectra(job.id)

        job.refresh_from_db()
        assert job.status == SoilAnalysisJob.Status.SUCCESS
        assert job.predicted_properties["SOM"] == 2.5
        assert job.predicted_properties["sample_count"] == 1
        assert job.model_version == tasks.CURRENT_MODEL_VERSION
        assert job.is_billable

    def test_batch_returns_one_prediction_per_row(self, org, fake_model):
        job = self.make_job(org, [[0.45] * N_FEATURES] * 3)

        tasks.analyze_soil_spectra(job.id)

        job.refresh_from_db()
        assert job.predicted_properties["SOM"] == [2.5, 2.5, 2.5]

    def test_shape_mismatch_fails_and_refunds(self, org, fake_model):
        job = self.make_job(org, [1.0, 2.0, 3.0])

        tasks.analyze_soil_spectra(job.id)

        job.refresh_from_db()
        assert job.status == SoilAnalysisJob.Status.FAILED
        assert "Shape mismatch" in job.error_message
        assert job.is_billable is False

    def test_missing_model_fails_job_instead_of_leaving_it_pending(self, org, monkeypatch):
        monkeypatch.setattr(tasks, "metrics_model", None)
        job = self.make_job(org, [[0.45] * N_FEATURES])

        tasks.analyze_soil_spectra(job.id)

        job.refresh_from_db()
        assert job.status == SoilAnalysisJob.Status.FAILED
        assert job.is_billable is False


class TestDashboard:
    def test_aggregates_my_org_jobs(self, client_for, org, owner, field, other_org):
        SoilAnalysisJob.objects.create(
            organization=org, field=field, status="SUCCESS", predicted_properties={"SOM": 2.0}
        )
        SoilAnalysisJob.objects.create(
            organization=org, field=field, status="SUCCESS", predicted_properties={"SOM": 3.0}
        )
        SoilAnalysisJob.objects.create(organization=org, field=field, status="FAILED")
        SoilAnalysisJob.objects.create(organization=other_org, status="SUCCESS", predicted_properties={"SOM": 9.0})

        response = client_for(owner).get(DASHBOARD_URL)

        assert response.status_code == 200
        assert response.data["total_samples_all_time"] == 3
        assert response.data["total_samples_this_month"] == 3
        assert response.data["average_som"] == 2.5
        by_status = {row["status"]: row["total"] for row in response.data["jobs_by_status"]}
        assert by_status == {"SUCCESS": 2, "FAILED": 1}

    def test_viewer_can_read_dashboard(self, client_for, org, make_member):
        viewer = make_member(org, Membership.VIEWER)

        response = client_for(viewer).get(DASHBOARD_URL)

        assert response.status_code == 200
        assert response.data["total_samples_all_time"] == 0
