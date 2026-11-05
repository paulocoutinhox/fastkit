from schemas.base_schema import BaseSchema


class VisitorSchema(BaseSchema):
    """A name signed by this side, which an application keeps and sends back when it counts a banner."""

    visitor: str
