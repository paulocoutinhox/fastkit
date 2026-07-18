import json

from fastkit_admin.assets import AssetRegistry

FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111827'/%3E%3Ctext x='16' y='23' font-family='Arial,sans-serif' font-size='20' font-weight='bold' fill='white' text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E"


def build_login_config(login: dict | None) -> dict:
    """Declarative login-form config: the identifier field, an optional identifier-type selector, the
    password toggle and OAuth buttons — so a consumer renders any login (email, username, a selector,
    OAuth-only, …) without editing the template. OAuth buttons link to consumer-owned callback URLs."""

    login = login or {}

    return {
        "identifier": login.get("identifier", {"label": "login.email", "type": "email", "autocomplete": "username", "default": ""}),
        "identifier_type": login.get("identifier_type", "email"),
        "identifier_types": login.get("identifier_types", []),
        "password": login.get("password", True),
        "oauth": login.get("oauth", []),
    }


def build_page_config(admin_settings, theme: dict | None = None, captcha: dict | None = None, login: dict | None = None, static_base: str = "/admin-static", registry: AssetRegistry | None = None) -> dict:
    """Build the context every admin template receives, including the client bootstrap JSON.

    `captcha` is the active captcha provider's `client_config()` dict (or None/disabled) and `login`
    is the declarative login-form config — the login screen renders itself from both, so any captcha
    provider and any login layout works without a template change.
    """

    theme = theme or {}
    registry = registry or AssetRegistry.discover()
    captcha = captcha or {"provider": None, "enabled": False}
    login_config = build_login_config(login)

    config = {
        "path": admin_settings.path,
        "api_path": admin_settings.api_path,
        "static_base": static_base,
        "favicon": theme.get("favicon", FAVICON),
        "brand_name": theme.get("brand_name", "FastKit"),
        "logo_url": theme.get("logo_url"),
        "logo_max_height": theme.get("logo_max_height", 32),
        "primary_color": theme.get("primary_color"),
        "forced_locale": theme.get("forced_locale"),
        "captcha": captcha,
        "login": login_config,
        "head_assets": registry.tags("css"),
        "body_assets": registry.tags("js"),
    }

    config["client"] = {
        "apiBaseUrl": config["api_path"],
        "adminPath": config["path"],
        "brand": {
            "name": config["brand_name"],
            "primaryColor": config["primary_color"],
        },
        "captcha": captcha,
        "login": {"identifierType": login_config["identifier_type"]},
    }

    return config


def render_client_json(config: dict, locale: str, messages: dict) -> str:
    """Serialize the per-request client bootstrap, safe to inline inside a <script> element."""

    payload = json.dumps({**config["client"], "locale": locale, "messages": messages})

    return (payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace(" ", "\\u2028").replace(" ", "\\u2029"))


def make_t(translator, locale: str):
    if translator is None:
        return lambda key, **params: key

    return lambda key, **params: translator.gettext(key, locale=locale, **params)


def request_config(config: dict, translator, locale: str) -> dict:
    messages = translator.messages(locale) if translator is not None else {}

    return {**config, "client_json": render_client_json(config, locale, messages)}
