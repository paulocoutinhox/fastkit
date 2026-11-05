from schemas.currency_reference import CurrencyReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class UserBalanceSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    currency_id: int
    currency: CurrencyReference | None
    amount: int
