from enum import StrEnum


class NewsletterStatus(StrEnum):
    """Where one subscription stands, where only a confirmed one is ever written to."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    UNSUBSCRIBED = "unsubscribed"
