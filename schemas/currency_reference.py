from schemas.base_schema import BaseSchema


class CurrencyReference(BaseSchema):
    id: int
    uuid: str
    code: str
    name: str
    symbol: str | None
