import logging

import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def check_redis():
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1, socket_timeout=1)
    client.ping()


CHECKS = {
    "database": check_database,
    "redis": check_redis,
}


def health_check(request):
    """
    GET /healthz: 200 when the database and Redis (Celery broker) answer, 503 otherwise.
    No auth, so load balancers, Docker and uptime monitors can call it.
    """
    results = {}
    for name, check in CHECKS.items():
        try:
            check()
            results[name] = "ok"
        except Exception:
            logger.exception(f"Health check failed: {name}")
            results[name] = "error"

    healthy = all(result == "ok" for result in results.values())
    return JsonResponse(
        {"status": "ok" if healthy else "error", "checks": results},
        status=200 if healthy else 503,
    )