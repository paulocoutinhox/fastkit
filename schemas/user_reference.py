from schemas.named_account import NamedAccount


class UserReference(NamedAccount):
    id: int
    username: str | None
    email: str | None
    nickname: str | None
    first_name: str | None
    last_name: str | None
    mobile_phone: str | None
    document: str | None
