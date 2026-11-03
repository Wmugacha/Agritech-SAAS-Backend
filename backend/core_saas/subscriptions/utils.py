import logging

from django.utils import timezone

from predictions.models import SoilAnalysisJob

from .models import Subscription

logger = logging.getLogger(__name__)


def check_subscription_limit(organization, feature_slug="predictions", lock=False):
    """
    Checks if an organization is allowed to use a feature based on their plan.
    Returns: (bool, str) -> (Allowed?, Reason)

    lock=True takes a row lock on the subscription (SELECT ... FOR UPDATE), so a
    concurrent request for the same organization waits until this transaction
    commits. Must be called inside transaction.atomic().
    """
    if not organization:
        logger.warning("Check limit called with no organization")
        return False, "No organization context"

    # Efficiently fetch subscription related to org
    try:
        if lock:
            sub = Subscription.objects.select_for_update().get(organization=organization)
        else:
            sub = organization.subscription
    except Subscription.DoesNotExist:
        logger.error(f"Organization {organization.id} has no subscription!")
        return False, "No active subscription found"

    if sub.status != Subscription.Status.ACTIVE:
        return False, "Subscription is not active"

    limit = sub.limits.get(feature_slug, 0)
    used = get_monthly_usage(organization, feature_slug)

    logger.info(f"Checking limit for {organization.name}: Plan {sub.plan} used {used}/{limit} {feature_slug}")

    if used >= limit:
        return False, f"{sub.get_plan_display()} allows {limit} {feature_slug} per month"

    return True, "OK"


def get_monthly_usage(organization, feature_slug="predictions"):
    """
    Counts billable usage since the start of the current calendar month.
    Failed jobs are marked is_billable=False by the worker, so they don't count.
    """
    if feature_slug != "predictions":
        return 0

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return SoilAnalysisJob.objects.filter(
        organization=organization,
        is_billable=True,
        created_at__gte=month_start,
    ).count()
