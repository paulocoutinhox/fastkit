from enum import StrEnum


class ConsentCategory(StrEnum):
    """What a visitor is asked about, where `necessary` is the one nobody is asked about because the site cannot answer without it."""

    NECESSARY = "necessary"
    PREFERENCES = "preferences"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
