from enum import StrEnum


class ResumeDeliveryPolicy(StrEnum):
    """What a plan owes a subscription that moves onto it, where coming back to the same plan always keeps the cycle it lands in."""

    SAME_CYCLE = "same-cycle"
    NEW_CYCLE = "new-cycle"
