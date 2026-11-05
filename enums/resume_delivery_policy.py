from enum import StrEnum


class ResumeDeliveryPolicy(StrEnum):
    """What a plan owes somebody who comes back, where coming back is most often a bill paid late."""

    SAME_CYCLE = "same-cycle"
    NEW_CYCLE = "new-cycle"
