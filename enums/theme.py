from enum import StrEnum


class Theme(StrEnum):
    """Which palette a page is drawn in, where `system` is what the device already asked for."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
