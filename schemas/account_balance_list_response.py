from schemas.account_balance_schema import AccountBalanceSchema
from schemas.base_schema import BaseSchema


class AccountBalanceListResponse(BaseSchema):
    items: list[AccountBalanceSchema]
