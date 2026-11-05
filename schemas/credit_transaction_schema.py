from enums.credit_transaction_type import CreditTransactionType
from schemas.currency_reference import CurrencyReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class CreditTransactionSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    currency_id: int
    currency: CurrencyReference | None
    benefit_grant_id: int | None
    type: CreditTransactionType
    amount: int
    balance_after: int
    idempotency_key: str
    description: str | None
    meta: dict
