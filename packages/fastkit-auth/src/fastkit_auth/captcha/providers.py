from fastkit_core.providers import ProviderRegistry
from fastkit_auth.captcha.disabled import DisabledCaptchaProvider
from fastkit_auth.captcha.image import ImageCaptchaProvider
from fastkit_auth.captcha.recaptcha import (
    GoogleRecaptchaClient,
    RecaptchaConfig,
    RecaptchaProvider,
    StaticRecaptchaClient,
)

captcha_providers = ProviderRegistry("captcha")


def build_disabled(settings, store):
    return DisabledCaptchaProvider()


def build_recaptcha(settings, store):
    captcha = settings.auth.captcha
    config = RecaptchaConfig(
        action=captcha.action,
        minimum_score=captcha.minimum_score,
        allowed_hostnames=tuple(captcha.allowed_hostnames),
    )
    client = (
        GoogleRecaptchaClient(captcha.secret_key, captcha.timeout_seconds)
        if captcha.secret_key
        else StaticRecaptchaClient(
            {"success": True, "action": captcha.action, "score": 1.0}
        )
    )

    return RecaptchaProvider(config, client, captcha.site_key, store)


def build_image(settings, store):
    captcha = settings.auth.captcha

    return ImageCaptchaProvider(
        store, length=captcha.image_length, ttl_seconds=captcha.challenge_ttl_seconds
    )


captcha_providers.register("disabled", build_disabled)
captcha_providers.register("recaptcha", build_recaptcha)
captcha_providers.register("image", build_image)
