from schemas.base_schema import BaseSchema


class PermissionsResponse(BaseSchema):
    """The resources and the reports this account reaches, which is what the panel draws a menu out of."""

    resources: list[str]
    reports: list[str]

    # An account that belongs to a brand writes into that brand and no other, so the panel stops drawing a field with one option.
    confined: bool

    # Whether the instance serves many brands, because where it serves one there is no brand to choose, filter by or show.
    brands: bool
