from schemas.base_schema import BaseSchema


class UserGroupReference(BaseSchema):
    id: int
    code: str
    name: str
