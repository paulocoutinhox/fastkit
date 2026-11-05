from enums.credit_transaction_type import CreditTransactionType
from schemas.currency_reference import CurrencyReference
from schemas.timestamp_schema import TimestampSchema


class AccountCreditSchema(TimestampSchema):
    """The ledger of whoever is asking, so naming the account in every line would say nothing."""

    id: int
    currency: CurrencyReference | None
    type: CreditTransactionType
    amount: int
    balance_after: int
    description: str | None
