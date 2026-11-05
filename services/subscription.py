from enums.benefit_policy import BenefitPolicy
from enums.subscription_status import SubscriptionStatus
from models.plan import Plan
from models.subscription import Subscription


def benefit_policy_of(subscription: Subscription, plan: Plan) -> BenefitPolicy:
    """What a subscription hands over in the state it is in, which trial and grace narrow and nothing else does."""
    if subscription.status == SubscriptionStatus.TRIALING:
        return plan.trial_benefit_policy

    if subscription.status == SubscriptionStatus.GRACE_PERIOD:
        return plan.grace_benefit_policy

    return BenefitPolicy.ALL
