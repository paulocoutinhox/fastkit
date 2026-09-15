from enum import StrEnum


class CaptchaProvider(StrEnum):
    """Which challenge a public form carries, where `disabled` is a choice an environment makes and never what a failure falls back to."""

    IMAGE = "image"
    RECAPTCHA_V3 = "recaptcha_v3"
    DISABLED = "disabled"
