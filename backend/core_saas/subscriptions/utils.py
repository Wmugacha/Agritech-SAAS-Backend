import logging
from .models import Subscription

logger = logging.getLogger(__name__)

def check_subscription_limit(organization, feature_slug="predictions"):
    """
    Checks if an organization is allowed to use a feature based on their plan.
    Returns: (bool, str) -> (Allowed?, Reason)
    """
    if not organization:
        logger.warning("Check limit called with no organization")
        return False, "No organization context"

    # Efficiently fetch subscription related to org
    try:
        sub = organization.subscription
    except Subscription.DoesNotExist:
        logger.error(f"Organization {organization.id} has no subscription!")
        return False, "No active subscription found"

    if sub.status != Subscription.Status.ACTIVE:
        return False, "Subscription is not active"

    # Check existence. 
    limit = sub.limits.get(feature_slug, 0)
    
    # log the check. 
    logger.info(f"Checking limit for {organization.name}: Plan {sub.plan} allows {limit} {feature_slug}")

    return True, "OK"