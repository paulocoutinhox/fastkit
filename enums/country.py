from enum import StrEnum


class PostalCodeProvider(StrEnum):
    """Who answers what a postal code stands for, which is a service of one country and never a worldwide one."""

    VIACEP = "viacep"
