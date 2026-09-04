from pydantic import Field

from enums.account import CreditTransactionType
from schemas.common import Amount, BaseSchema, OptionalReference, Position, Reference, Text, TimestampSchema, as_optional
from schemas.tenant import TenantReference
from schemas.user import UserReference


class CurrencyReference(BaseSchema):
    id: int
    uuid: str
    code: str
    name: str
    symbol: str | None


class CurrencySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    code: str
    name: str
    symbol: str | None
    position: int
    active: bool
    meta: dict


class CurrencyCreate(BaseSchema):
    tenant_id: OptionalReference
    code: str | None = Field(None, max_length=32)
    name: Text(128)
    symbol: str | None = Field(None, max_length=8)
    position: Position
    active: bool = True
    meta: dict = Field(default_factory=dict)


CurrencyUpdate = as_optional("CurrencyUpdate", CurrencyCreate)


class UserBalanceSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    currency_id: int
    currency: CurrencyReference | None
    amount: int


class AccountBalanceSchema(BaseSchema):
    """What the account holds of one currency, which is the running total the ledger of that currency explains."""

    currency: CurrencyReference
    amount: int


class AccountBalanceListResponse(BaseSchema):
    items: list[AccountBalanceSchema]


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


class AccountCreditSchema(TimestampSchema):
    """The ledger of whoever is asking, so naming the account in every line would say nothing."""

    id: int
    currency: CurrencyReference | None
    type: CreditTransactionType
    amount: int
    balance_after: int
    description: str | None


class CreditTransactionCreate(BaseSchema):
    user_id: Reference
    currency_id: Reference
    type: CreditTransactionType
    amount: Amount
    description: str | None = Field(None, max_length=255)
    meta: dict = Field(default_factory=dict)
