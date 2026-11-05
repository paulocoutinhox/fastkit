from sqlalchemy import select

from models.benefit_grant import BenefitGrant
from models.subscription import Subscription
from models.subscription_benefit import SubscriptionBenefit
from services.crud_service import CrudService
from services.elsewhere import Elsewhere
from services.reach import Reach


class BenefitGrantService(CrudService):
    model = BenefitGrant
    reaches_through = Reach(BenefitGrant.subscription_benefit_id, SubscriptionBenefit, Reach(SubscriptionBenefit.subscription_id, Subscription))
    search_fields = ("grant_key", "cycle_key")
    filter_fields = ("user_id", "status")
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: BenefitGrant.subscription_benefit_id.in_(select(SubscriptionBenefit.id).where(SubscriptionBenefit.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))))}
    ordering_fields = ("id", "scheduled_at", "status", "created_at")
    default_ordering = "-id"
    relations = ("subscription_benefit.subscription.user",)
    label_fields = ("grant_key",)


benefit_grant_service = BenefitGrantService()
