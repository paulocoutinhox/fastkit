from pydantic import Field

from enums.credit_transaction_type import CreditTransactionType
from schemas.base_schema import BaseSchema
from schemas.common import Amount, JsonMap, Reference


class CreditTransactionCreate(BaseSchema):
    user_id: Reference
    currency_id: Reference
    type: CreditTransactionType
    amount: Amount
    description: str | None = Field(None, max_length=255)
    meta: JsonMap = Field(default_factory=dict)
