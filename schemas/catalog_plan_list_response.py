from schemas.base_schema import BaseSchema
from schemas.catalog_plan_schema import CatalogPlanSchema


class CatalogPlanListResponse(BaseSchema):
    items: list[CatalogPlanSchema]
