from enum import StrEnum


class UserAddressType(StrEnum):
    MAIN = "main"
    BILLING = "billing"
    SHIPPING = "shipping"
