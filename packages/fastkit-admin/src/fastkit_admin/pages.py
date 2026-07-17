import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import NotFoundError
from fastkit_admin.api import check_permission, make_check
from fastkit_admin.assets import AssetRegistry
from fastkit_admin.query import parse_grid_query
from fastkit_admin.screens import detail_context, form_context, list_context, profile_context, report_context

STATIC_DIR = Path(__file__).parent / "static"

FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111827'/%3E%3Ctext x='16' y='23' font-family='Arial,sans-serif' font-size='20' font-weight='bold' fill='white' text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E"


def mount_assets(app, registry: AssetRegistry | None = None) -> None:
    """Serve every vendored front-end asset package from its own url prefix."""

    registry = registry or AssetRegistry.discover()

    for mount, directory in registry.mounts():
        app.mount(mount, StaticFiles(directory=directory), name=f"vendor-{mount.rsplit('/', 1)[-1]}")


def mount_admin_static(app, static_base: str = "/admin-static", registry: AssetRegistry | None = None) -> None:
    """Serve the admin client (app.js/admin.css) and every vendored asset package.

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


def resolve_route(sub: str) -> tuple[str, dict]:
    """Map an admin sub-path to a screen kind and its arguments."""

    parts = [part for part in sub.split("/") if part]

    if not parts:
        return "dashboard", {}

    if len(parts) == 1:
        if parts[0] == "profile":
            return "profile", {}

        return "list", {"resource": parts[0]}

    if len(parts) == 2:
        if parts[0] == "reports":
            return "report", {"name": parts[1]}

        if parts[1] == "new":
            return "form", {"resource": parts[0], "record_id": None, "mode": "create"}

        return "detail", {"resource": parts[0], "record_id": parts[1]}

    if len(parts) == 3 and parts[2] == "edit":
        return "form", {"resource": parts[0], "record_id": parts[1], "mode": "edit"}

    return "notfound", {}


async def list_screen(target, session, check, locale: str, path: str, params) -> dict:
    query = parse_grid_query(params)
    result = await target.list(session, query, locale)
    flags = await target.permission_flags(check)

    return list_context(target.grid_schema(flags), result, path, query.search, query.sort, query.filters)


async def form_screen(target, session, locale: str, path: str, record_id, mode: str) -> dict:
    values = None

    if record_id is not None:
        values = target.serialize_detail(await target.get_object(session, record_id), locale)

    return form_context(target.form_schema(mode), values, target.label or target.name, mode, path, target.name, record_id=record_id)


async def detail_screen(target, session, check, locale: str, path: str, record_id) -> dict:
    data = target.serialize_detail(await target.get_object(session, record_id), locale)
    flags = await target.permission_flags(check)

    return detail_context(target.form_schema("edit"), data, target.label or target.name, path, target.name, str(record_id), flags)


def _screen_query(params) -> str:
    items = [(key, value) for key, value in params.multi_items() if key != "_fragment"]

    return f"?{urlencode(items)}" if items else ""


def build_admin_pages_router(renderer, site, deps, config: dict, avatar_url=None, translator=None, report_data=None, profile_data=None) -> APIRouter:
    """Serve the server-rendered admin (login, dashboard, and every resource/report/profile screen).

    Screens are rendered from consumer-overridable Jinja templates. ``report_data(name, session,
    locale, params)`` and ``profile_data(user, locale)`` are async providers the consumer wires from
    its report and account services. The client message catalog comes from ``translator`` (falling
    back to the one wired on ``deps``).
    """

    router = APIRouter()
    path = config["path"]
    api_path = config["api_path"]
    translator = translator if translator is not None else deps.translator

    async def resolve_locale(request: Request) -> str:
        return config["forced_locale"] or await deps.get_locale(request)

    def make_t(locale: str):
        if translator is None:
            return lambda key, **params: key

        return lambda key, **params: translator.gettext(key, locale=locale, **params)

    def request_config(locale: str) -> dict:
        messages = translator.messages(locale) if translator is not None else {}

        return {**config, "client_json": render_client_json(config, locale, messages)}

    async def shell(user, locale: str) -> dict:
        navigation = await site.navigation(make_check(deps.authorize, user))

        if deps.translate is not None:
            for group in navigation:
                group["label"] = deps.translate(group["label"], locale)

                for item in group["items"]:
                    item["label"] = deps.translate(item["label"], locale)

        asset_id = user.profile.avatar_asset_id if getattr(user, "profile", None) else None
        avatar = await avatar_url(asset_id) if (avatar_url is not None and asset_id) else None

        display_name = user.display_name or getattr(user, "email", None) or "User"

        return {"config": request_config(locale), "navigation": navigation, "user": {"display_name": display_name, "timezone": getattr(user, "timezone", None) or "UTC", "avatar_url": avatar}, "t": make_t(locale)}

    @router.get(f"{path}/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        locale = await resolve_locale(request)

        return HTMLResponse(renderer.render("admin/login.html", config=request_config(locale)))

    @router.get(path, response_class=HTMLResponse)
    async def root_page(request: Request, user=Depends(deps.get_optional_user)):
        if user is None:
            return RedirectResponse(f"{path}/login", status_code=303)

        locale = await resolve_locale(request)

        return HTMLResponse(renderer.render("admin/dashboard.html", **await shell(user, locale)))

    @router.get(f"{path}/{{sub:path}}", response_class=HTMLResponse)
    async def sub_page(request: Request, sub: str, user=Depends(deps.get_optional_user), session=Depends(deps.get_session)):
        if user is None:
            return RedirectResponse(f"{path}/login", status_code=303)

        locale = await resolve_locale(request)
        check = make_check(deps.authorize, user)
        kind, args = resolve_route(sub)
        fragment = request.query_params.get("_fragment") == "table"

        if kind == "dashboard":
            return HTMLResponse(renderer.render("admin/dashboard.html", **await shell(user, locale)))

        if kind == "profile":
            data = await profile_data(user, locale) if profile_data is not None else {}

            return HTMLResponse(renderer.render("admin/profile.html", **await shell(user, locale), **profile_context(data, path, api_path)))

        if kind == "report":
            if report_data is None:
                raise NotFoundError(RESOURCE_NOT_FOUND, message="report not found")

            context = report_context(await report_data(args["name"], session, locale, dict(request.query_params)), args["name"], path, api_path, _screen_query(request.query_params))

            if fragment:
                return HTMLResponse(renderer.render("admin/partials/_report_table.html", t=make_t(locale), **context))

            return HTMLResponse(renderer.render("admin/report.html", **await shell(user, locale), **context))

        if kind == "notfound":
            raise NotFoundError(RESOURCE_NOT_FOUND, message="not found")

        target = site.get(args["resource"])

        if kind == "list":
            await check_permission(deps.authorize, user, target, "list")
            context = await list_screen(target, session, check, locale, path, request.query_params)

            if fragment:
                return HTMLResponse(renderer.render("admin/partials/_table.html", t=make_t(locale), **context))

            return HTMLResponse(renderer.render("admin/list.html", **await shell(user, locale), **context))

        if kind == "form":
            await check_permission(deps.authorize, user, target, "create" if args["mode"] == "create" else "update")

            return HTMLResponse(renderer.render("admin/form.html", **await shell(user, locale), **await form_screen(target, session, locale, path, args["record_id"], args["mode"])))

        await check_permission(deps.authorize, user, target, "detail")

        return HTMLResponse(renderer.render("admin/detail.html", **await shell(user, locale), **await detail_screen(target, session, check, locale, path, args["record_id"])))

    return router
