from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import AuthorizationError, NotFoundError
from fastkit_admin.api import check_permission, make_check
from fastkit_admin.page_config import make_t, request_config
from fastkit_admin.query import parse_grid_query
from fastkit_admin.routing import build_header, nav_current, resolve_route, screen_query
from fastkit_admin.screens import detail_context, form_context, list_context, profile_context, report_context


@dataclass(frozen=True)
class PagesDeps:
    renderer: object
    site: object
    deps: object
    config: dict
    translator: object
    avatar_url: object
    report_data: object
    profile_data: object


async def list_screen(target, session, check, locale: str, path: str, params) -> dict:
    query = parse_grid_query(params)
    result = await target.list(session, query, locale)
    flags = await target.permission_flags(check)

    return list_context(target.grid_schema(flags), result, path, query.search, query.sort, query.filters)


async def _attach_related_flags(schema: dict, site, check) -> None:
    for group in schema["fieldsets"] + schema.get("inlines", []):
        for field in group["fields"]:
            related = site.find(field["related"]) if field.get("related") else None

            if related is None:
                continue

            flags = await related.permission_flags(check)
            field["related_flags"] = {"add": flags["can_create"], "edit": flags["can_update"], "delete": flags["can_delete"]}


async def form_screen(target, session, check, site, locale: str, path: str, record_id, mode: str) -> dict:
    schema = target.form_schema(mode)
    await _attach_related_flags(schema, site, check)
    values = None
    inline_data = None

    if record_id is not None:
        row = await target.get_object(session, record_id)
        values = target.serialize_detail(row, locale)
        inline_data = await target.inline_values(session, row, locale)

    flags = await target.permission_flags(check)

    return form_context(schema, values, target.label or target.name, mode, path, target.name, record_id=record_id, inline_data=inline_data, flags=flags)


async def detail_screen(target, session, check, locale: str, path: str, record_id) -> dict:
    data = target.serialize_detail(await target.get_object(session, record_id), locale)
    flags = await target.permission_flags(check)

    return detail_context(target.form_schema("edit"), data, target.label or target.name, path, target.name, str(record_id), flags)


async def shell_context(pages: PagesDeps, user, locale: str, current: str | None = None, breadcrumb: list[dict] | None = None, page_title: str = "") -> dict:
    navigation = await pages.site.navigation(make_check(pages.deps.authorize, user))

    if pages.deps.translate is not None:
        for group in navigation:
            group["label"] = pages.deps.translate(group["label"], locale)

            for item in group["items"]:
                item["label"] = pages.deps.translate(item["label"], locale)

    file_id = user.profile.avatar_file_id if getattr(user, "profile", None) else None
    avatar = await pages.avatar_url(file_id) if (pages.avatar_url is not None and file_id) else None
    display_name = user.display_name or getattr(user, "email", None) or "User"

    return {"config": request_config(pages.config, pages.translator, locale), "navigation": navigation, "current": current, "breadcrumb": breadcrumb, "page_title": page_title, "user": {"display_name": display_name, "timezone": getattr(user, "timezone", None) or "UTC", "avatar_url": avatar}, "t": make_t(pages.translator, locale)}


async def _forbidden(pages: PagesDeps, user, locale: str, current: str | None = None) -> HTMLResponse:
    message = make_t(pages.translator, locale)("error.forbidden")

    return HTMLResponse(pages.renderer.render("admin/error.html", **await shell_context(pages, user, locale, current), message=message), status_code=403)


async def dispatch_screen(pages: PagesDeps, sub: str, params, user, session, locale: str) -> HTMLResponse:
    path = pages.config["path"]
    api_path = pages.config["api_path"]
    render = pages.renderer.render
    kind, args = resolve_route(sub)
    current = nav_current(kind, args)
    fragment = params.get("_fragment")
    check = make_check(pages.deps.authorize, user)
    t = make_t(pages.translator, locale)

    if kind == "dashboard":
        crumb, title = build_header(kind, args, path, t)

        return HTMLResponse(render("admin/dashboard.html", **await shell_context(pages, user, locale, current, crumb, title)))

    if kind == "profile":
        data = await pages.profile_data(user, locale) if pages.profile_data is not None else {}
        crumb, title = build_header(kind, args, path, t)

        return HTMLResponse(render("admin/profile.html", **await shell_context(pages, user, locale, current, crumb, title), **profile_context(data, path, api_path)))

    if kind == "report":
        if pages.report_data is None:
            raise NotFoundError(RESOURCE_NOT_FOUND, message="report not found")

        try:
            data = await pages.report_data(args["name"], session, locale, dict(params), check)
        except AuthorizationError:
            return await _forbidden(pages, user, locale, current)

        context = report_context(data, args["name"], path, api_path, screen_query(params))

        if fragment == "table":
            return HTMLResponse(render("admin/partials/_report_table.html", t=t, **context))

        crumb, title = build_header(kind, args, path, t, report_title=context["title"])

        return HTMLResponse(render("admin/report.html", **await shell_context(pages, user, locale, current, crumb, title), **context))

    if kind == "notfound":
        raise NotFoundError(RESOURCE_NOT_FOUND, message="not found")

    target = pages.site.get(args["resource"])
    label = target.label or target.name

    try:
        if kind == "list":
            await check_permission(pages.deps.authorize, user, target, "list")
            context = await list_screen(target, session, check, locale, path, params)

            if fragment == "table":
                return HTMLResponse(render("admin/partials/_table.html", t=t, **context))

            crumb, title = build_header(kind, args, path, t, label=label)

            return HTMLResponse(render("admin/list.html", **await shell_context(pages, user, locale, current, crumb, title), **context))

        if kind == "form":
            await check_permission(pages.deps.authorize, user, target, "create" if args["mode"] == "create" else "update")
            context = await form_screen(target, session, check, pages.site, locale, path, args["record_id"], args["mode"])

            if fragment == "form":
                return HTMLResponse(render("admin/partials/_form.html", t=t, **context))

            crumb, title = build_header(kind, args, path, t, label=label)

            return HTMLResponse(render("admin/form.html", **await shell_context(pages, user, locale, current, crumb, title), **context))

        await check_permission(pages.deps.authorize, user, target, "detail")
        detail = await detail_screen(target, session, check, locale, path, args["record_id"])
        crumb, title = build_header(kind, args, path, t, label=label, display=detail.get("display"))

        return HTMLResponse(render("admin/detail.html", **await shell_context(pages, user, locale, current, crumb, title), **detail))
    except AuthorizationError:
        return await _forbidden(pages, user, locale, current)


async def render_login(pages: PagesDeps, request: Request) -> HTMLResponse:
    locale = pages.config["forced_locale"] or await pages.deps.get_locale(request)

    return HTMLResponse(pages.renderer.render("admin/login.html", config=request_config(pages.config, pages.translator, locale), t=make_t(pages.translator, locale)))


async def render_screen(pages: PagesDeps, request: Request, sub: str, user, session):
    if user is None:
        return RedirectResponse(f'{pages.config["path"]}/login', status_code=303)

    locale = pages.config["forced_locale"] or await pages.deps.get_locale(request)

    return await dispatch_screen(pages, sub, request.query_params, user, session, locale)


def build_admin_pages_router(renderer, site, deps, config: dict, avatar_url=None, translator=None, report_data=None, profile_data=None) -> APIRouter:
    """Serve the server-rendered admin (login, dashboard, and every resource/report/profile screen).

    Screens are rendered from consumer-overridable Jinja templates. ``report_data(name, session,
    locale, params)`` and ``profile_data(user, locale)`` are async providers the consumer wires from
    its report and account services. The client message catalog comes from ``translator`` (falling
    back to the one wired on ``deps``).
    """

    router = APIRouter()
    path = config["path"]
    pages = PagesDeps(renderer, site, deps, config, translator if translator is not None else deps.translator, avatar_url, report_data, profile_data)

    @router.get(f"{path}/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return await render_login(pages, request)

    @router.get(path, response_class=HTMLResponse)
    async def root_page(request: Request, user=Depends(deps.get_optional_user)):
        return await render_screen(pages, request, "", user, None)

    @router.get(f"{path}/{{sub:path}}", response_class=HTMLResponse)
    async def sub_page(request: Request, sub: str, user=Depends(deps.get_optional_user), session=Depends(deps.get_session)):
        return await render_screen(pages, request, sub, user, session)

    return router
