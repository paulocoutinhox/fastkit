from helpers.storage import storage
from schemas.catalog_entry_schema import CatalogEntrySchema


def product_card(product) -> CatalogEntrySchema:
    """A product card is what the site and an application are answered the same, so it is assembled once instead of once per surface."""
    return CatalogEntrySchema(
        id=product.id,
        uuid=product.uuid,
        name=product.name,
        slug=product.slug,
        description=product.description,
        image_url=storage.url(product.image) if product.image else None,
        currency=product.currency,
        price=product.price,
        credits=product.credits,
        credits_currency=product.credits_currency.name if product.credits_currency else None,
        featured=product.featured,
    )
