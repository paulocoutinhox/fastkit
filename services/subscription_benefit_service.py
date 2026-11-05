from sqlalchemy import select

from models.benefit_grant import BenefitGrant
from models.subscription import Subscription
from models.subscription_benefit import SubscriptionBenefit
from services.crud_service import CrudService
from services.dependent import Dependent
from services.elsewhere import Elsewhere
from services.reach import Reach


class SubscriptionBenefitService(CrudService):
    model = SubscriptionBenefit
    reaches_through = Reach(SubscriptionBenefit.subscription_id, Subscription)
    search_fields = ("target",)
    filter_fields = ("user_id", "benefit_id", "status", "benefit_type")
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: SubscriptionBenefit.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))}
    ordering_fields = ("id", "next_grant_at", "last_grant_at", "created_at")
    default_ordering = "-id"
    relations = ("subscription.user", "product", "currency")
    label_fields = ("target",)
    dependents = (Dependent(BenefitGrant, "subscription_benefit_id"),)


subscription_benefit_service = SubscriptionBenefitService()
