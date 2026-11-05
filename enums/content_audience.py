from enum import StrEnum


class ContentAudience(StrEnum):
    EVERYONE = "everyone"
    SIGNED_IN = "signed-in"
    MEMBERS = "members"
