from schemas.base_schema import BaseSchema
from schemas.catalog_product_schema import CatalogProductSchema


class ProductListResponse(BaseSchema):
    items: list[CatalogProductSchema]
