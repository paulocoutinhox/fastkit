from schemas.catalog_entry_schema import CatalogEntrySchema


class CatalogProductSchema(CatalogEntrySchema):
    """What a visitor reads, which is the catalogue plus the one thing that belongs to their account alone."""

    owned: bool
