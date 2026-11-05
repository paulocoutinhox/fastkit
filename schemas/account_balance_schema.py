from schemas.base_schema import BaseSchema
from schemas.currency_reference import CurrencyReference


class AccountBalanceSchema(BaseSchema):
    """What the account holds of one currency, which is the running total the ledger of that currency explains."""

    currency: CurrencyReference
    amount: int
