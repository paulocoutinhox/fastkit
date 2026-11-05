from schemas.base_schema import BaseSchema
from schemas.user_reference import UserReference


class SubscriptionReference(BaseSchema):
    id: int
    user: UserReference | None
