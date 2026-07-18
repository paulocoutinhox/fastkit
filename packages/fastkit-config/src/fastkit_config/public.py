from fastkit_config.settings import FastKitSettings

SENSITIVE_HINTS = ("secret", "password", "token", "key")


def public_frontend_config(settings: FastKitSettings) -> dict:
    """Return only the values that are safe to expose to the browser, never secrets."""

    captcha = settings.auth.captcha

    return {
        "environment": settings.app.environment,
        "adminApiBaseUrl": settings.admin.api_path,
        "locale": settings.i18n.default_locale,
        "supportedLocales": settings.i18n.supported_locales,
        "captcha": {
            "provider": captcha.provider,
            "siteKey": captcha.site_key,
            "action": captcha.action,
        },
        "features": {
            "darkMode": True,
            "contentEditor": settings.content.sanitize_html,
        },
    }


def is_sensitive_key(name: str) -> bool:
    lowered = name.lower()

    return any(hint in lowered for hint in SENSITIVE_HINTS)


def mask_value(value: str) -> str:
    if len(value) <= 4:
        return "****"

    return f"{value[:2]}****{value[-2:]}"
