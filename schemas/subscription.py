from helpers.storage import storage
from schemas.catalog_plan_schema import CatalogPlanSchema


def catalogued(plan) -> CatalogPlanSchema:
    """A plan is the one thing the site and an application are answered the same, so it is assembled once instead of once per surface."""
    return CatalogPlanSchema(
        id=plan.id,
        uuid=plan.uuid,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        image_url=storage.url(plan.image) if plan.image else None,
        currency=plan.currency,
        price=plan.price,
        billing_interval_unit=plan.billing_interval_unit,
        billing_interval_value=plan.billing_interval_value,
        featured=plan.featured,
    )
