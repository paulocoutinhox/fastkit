from schemas.account_entitlement_schema import AccountEntitlementSchema
from schemas.base_schema import BaseSchema


class AccountEntitlementListResponse(BaseSchema):
    items: list[AccountEntitlementSchema]
