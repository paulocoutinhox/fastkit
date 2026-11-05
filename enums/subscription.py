from enums.benefit_grant_status import BenefitGrantStatus
from enums.subscription_status import SubscriptionStatus

ELIGIBLE_SUBSCRIPTION_STATUSES = frozenset({SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD})


SCHEDULE_ADVANCE_STATUSES = frozenset({BenefitGrantStatus.COMPLETED, BenefitGrantStatus.SKIPPED})


# What a gateway naming its own state calls a subscription that is finished, so nothing here has to read it off the dates.
CLOSED_SUBSCRIPTION_STATUSES = frozenset({SubscriptionStatus.EXPIRED, SubscriptionStatus.REVOKED})
