from schemas.account_subscription_schema import AccountSubscriptionSchema
from schemas.base_schema import BaseSchema


class AccountSubscriptionListResponse(BaseSchema):
    items: list[AccountSubscriptionSchema]
