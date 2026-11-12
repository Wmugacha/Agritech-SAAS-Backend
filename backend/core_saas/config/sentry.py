import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration


def init_sentry(dsn, environment="production", traces_sample_rate=0.0, release=None):
    """
    Report unhandled errors from the web app and the Celery worker to Sentry.
    Does nothing without a DSN, so local development and CI never send events.

    Called from settings.py. The worker loads the same settings, so this also covers Celery.
    """
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        # Performance tracing is off by default to stay inside the free tier
        traces_sample_rate=traces_sample_rate,
        # Don't send emails, IPs or cookies
        send_default_pii=False,
    )
    return True