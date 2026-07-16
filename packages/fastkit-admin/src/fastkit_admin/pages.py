import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from fastkit_admin.api import make_check
from fastkit_admin.assets import AssetRegistry

STATIC_DIR = Path(__file__).parent / "static"

FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111827'/%3E%3Ctext x='16' y='23' font-family='Arial,sans-serif' font-size='20' font-weight='bold' fill='white' text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E"


def mount_assets(app, registry: AssetRegistry | None = None) -> None:
    """Serve every vendored front-end asset package from its own url prefix."""

    registry = registry or AssetRegistry.discover()

    for mount, directory in registry.mounts():
        app.mount(mount, StaticFiles(directory=directory), name=f"vendor-{mount.rsplit('/', 1)[-1]}")


def mount_admin_static(app, static_base: str = "/admin-static", registry: AssetRegistry | None = None) -> None:
    """Serve the admin client (admin.js/admin.css) and every vendored asset package.

    A consumer calls this once after building the application, so the admin frontend needs
    no per-project static wiring.
    """

    app.mount(static_base, StaticFiles(directory=STATIC_DIR), name="admin-static")
    mount_assets(app, registry)


def build_page_config(admin_settings, theme: dict | None = None, recaptcha=None, static_base: str = "/admin-static", registry: AssetRegistry | None = None) -> dict:
    """Build the context every admin template receives, including the client bootstrap JSON."""

    theme = theme or {}
    registry = registry or AssetRegistry.discover()

    recaptcha_enabled = bool(recaptcha and recaptcha.enabled)
    recaptcha_site_key = recaptcha.site_key if recaptcha_enabled else ""
    recaptcha_action = recaptcha.action if recaptcha_enabled else ""

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
        "recaptcha_enabled": recaptcha_enabled,
        "recaptcha_site_key": recaptcha_site_key,
        "recaptcha_action": recaptcha_action,
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
        "recaptcha": {
            "enabled": recaptcha_enabled,
            "siteKey": recaptcha_site_key,
            "action": recaptcha_action,
        },
    }

    return config


def render_client_json(config: dict, locale: str, messages: dict) -> str:
    """Serialize the per-request client bootstrap, safe to inline inside a <script> element."""

    payload = json.dumps({**config["client"], "locale": locale, "messages": messages})

    return (payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def build_admin_pages_router(renderer, site, deps, config: dict, avatar_url=None, translator=None) -> APIRouter:
    """Serve the server-rendered admin shell (login + app) with consumer-overridable templates.

    The client message catalog comes from ``translator`` (falling back to the one wired on
    ``deps`` by ``build_admin_deps``), so a project that uses ``build_admin_deps`` gets a fully
    localized client with no extra wiring.
    """

    router = APIRouter()
    path = config["path"]
    translator = translator if translator is not None else deps.translator

    async def resolve_locale(request: Request) -> str:
        return config["forced_locale"] or await deps.get_locale(request)

    def request_config(locale: str) -> dict:
        messages = translator.messages(locale) if translator is not None else {}

        return {**config, "client_json": render_client_json(config, locale, messages)}

    async def render_shell(request: Request):
        user = await deps.get_optional_user(request)

        if user is None:
            return RedirectResponse(f"{path}/login", status_code=303)

        locale = await resolve_locale(request)
        navigation = await site.navigation(make_check(deps.authorize, user))

        if deps.translate is not None:
            for group in navigation:
                group["label"] = deps.translate(group["label"], locale)

                for item in group["items"]:
                    item["label"] = deps.translate(item["label"], locale)

        asset_id = user.profile.avatar_asset_id if getattr(user, "profile", None) else None
        avatar = await avatar_url(asset_id) if (avatar_url is not None and asset_id) else None
        html = renderer.render("admin/app.html", config=request_config(locale), navigation=navigation, user={"display_name": user.display_name, "timezone": getattr(user, "timezone", None) or "UTC", "avatar_url": avatar})

        return HTMLResponse(html)

    @router.get(f"{path}/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        locale = await resolve_locale(request)

        return HTMLResponse(renderer.render("admin/login.html", config=request_config(locale)))

    @router.get(path, response_class=HTMLResponse)
    async def root_page(request: Request):
        return await render_shell(request)

    @router.get(f"{path}/{{sub:path}}", response_class=HTMLResponse)
    async def sub_page(request: Request, sub: str):
        return await render_shell(request)

    return router
