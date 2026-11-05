from enum import StrEnum


class BenefitCadence(StrEnum):
    ON_ACTIVATION = "on-activation"
    RECURRING = "recurring"
    ONCE_PER_USER = "once-per-user"
