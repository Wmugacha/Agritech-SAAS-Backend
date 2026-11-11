import json
import logging
import sys
from unittest import mock

import pytest
from django.db import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

from config import health
from config.log_formatters import JsonFormatter
from config.sentry import init_sentry

HEALTH_URL = "/healthz"

pytestmark = pytest.mark.django_db


class TestHealthCheck:
    def test_healthy_when_database_and_redis_answer(self, api_client):
        # CI runs a real Postgres and Redis, so this checks the real connections
        response = api_client.get(HEALTH_URL)

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}

    def test_no_auth_needed(self, api_client):
        # Load balancers and uptime monitors don't have a JWT
        assert api_client.get(HEALTH_URL).status_code != 401

    def test_redis_down_returns_503(self, api_client):
        with mock.patch.dict(
            health.CHECKS, {"redis": mock.Mock(side_effect=RedisConnectionError("refused"))}
        ):
            response = api_client.get(HEALTH_URL)

        assert response.status_code == 503
        assert response.json()["checks"] == {"database": "ok", "redis": "error"}

    def test_database_down_returns_503(self, api_client):
        with mock.patch.dict(health.CHECKS, {"database": mock.Mock(side_effect=OperationalError("gone"))}):
            response = api_client.get(HEALTH_URL)

        assert response.status_code == 503
        assert response.json()["checks"]["database"] == "error"


class TestJsonLogging:
    def make_record(self, **kwargs):
        return logging.LogRecord(
            name="predictions.tasks", level=logging.INFO, pathname=__file__, lineno=1,
            msg="Job %s finished", args=("abc",), exc_info=None, **kwargs,
        )

    def test_record_is_one_json_object_with_extras(self):
        record = self.make_record()
        record.job_id = "abc"  # what extra={"job_id": "abc"} does

        entry = json.loads(JsonFormatter().format(record))

        assert entry["level"] == "INFO"
        assert entry["logger"] == "predictions.tasks"
        assert entry["message"] == "Job abc finished"
        assert entry["job_id"] == "abc"
        assert "timestamp" in entry

    def test_exceptions_are_included(self):
        try:
            raise ValueError("bad spectra")
        except ValueError:
            record = self.make_record()
            record.exc_info = sys.exc_info()

        entry = json.loads(JsonFormatter().format(record))

        assert "ValueError: bad spectra" in entry["exception"]

    def test_json_is_the_default_format(self, settings):
        assert settings.LOGGING["handlers"]["console"]["formatter"] == "json"


class TestSentry:
    def test_disabled_without_dsn(self):
        with mock.patch("config.sentry.sentry_sdk.init") as init:
            assert init_sentry(dsn=None) is False
        init.assert_not_called()

    def test_enabled_with_django_and_celery_integrations(self):
        with mock.patch("config.sentry.sentry_sdk.init") as init:
            assert init_sentry(dsn="https://key@o0.ingest.sentry.io/1", environment="staging") is True

        kwargs = init.call_args.kwargs
        assert kwargs["environment"] == "staging"
        assert kwargs["send_default_pii"] is False
        assert {type(i).__name__ for i in kwargs["integrations"]} == {"DjangoIntegration", "CeleryIntegration"}
    