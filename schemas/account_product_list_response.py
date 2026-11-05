from schemas.account_product_schema import AccountProductSchema
from schemas.base_schema import BaseSchema


class AccountProductListResponse(BaseSchema):
    items: list[AccountProductSchema]
