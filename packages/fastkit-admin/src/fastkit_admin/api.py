from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, Request

from fastkit_core.api.envelope import build_message, success_envelope
from fastkit_admin.query import parse_grid_query
from fastkit_admin.site import AdminSite


@dataclass
class AdminDeps:
    get_session: Callable
    get_current_user: Callable
    get_locale: Callable
    authorize: Callable[[Any, str], Awaitable[None]] | None = None
    get_optional_user: Callable[[Any], Awaitable[Any]] | None = None
    audit: Callable[[str, str, str | None], Awaitable[None]] | None = None
    translate: Callable[[str, str | None], str] | None = None
    translator: Any = None


async def check_permission(authorize, user, resource, action: str) -> None:
    permission = resource.permissions.get(action)

    if permission and authorize is not None:
        await authorize(user, permission)


def make_check(authorize, user):
    """Return an async predicate answering whether the user holds a given permission."""

    async def check(permission: str) -> bool:
        if authorize is None:
            return True

        from fastkit_core.errors.exceptions import AuthorizationError

        try:
            await authorize(user, permission)

            return True
        except AuthorizationError:
            return False

    return check


async def handle_navigation(site, authorize, user) -> dict:
    groups = await site.navigation(make_check(authorize, user))

    return success_envelope(data=groups)


async def handle_schema(
    site, authorize, user, resource: str, mode: str, translate=None, locale=None
) -> dict:
    target = site.get(resource)
    flags = await target.permission_flags(make_check(authorize, user))
    tr = (lambda text: translate(text, locale)) if translate is not None else None

    return success_envelope(
        data={
            "grid": target.grid_schema(flags, tr),
            "form": target.form_schema(mode, tr),
        }
    )


async def handle_action(
    site,
    authorize,
    user,
    session,
    locale,
    resource: str,
    action_name: str,
    identifiers: list,
) -> dict:
    target = site.get(resource)
    action = target.get_action(action_name)

    if action.permission is not None:
        if authorize is not None:
            await authorize(user, action.permission)
    else:
        await check_permission(authorize, user, target, "update")

    result = await target.run_action(session, action_name, identifiers, locale)

    return success_envelope(
        data=result,
        message=build_message(
            f"{target.name}.{action_name}", f"{action.label} completed."
        ),
    )


async def handle_grid(site, authorize, user, session, locale, params) -> dict:
    target = site.get(params["resource"])
    await check_permission(authorize, user, target, "list")

    result = await target.list(session, parse_grid_query(params["query"]), locale)

    return success_envelope(
        data=result["rows"], meta_extra={"pagination": result["pagination"]}
    )


async def handle_detail(
    site, authorize, user, session, locale, resource: str, identifier: str
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "detail")

    row = await target.get_object(session, identifier)

    return success_envelope(data=target.serialize_detail(row, locale))


async def handle_grid_row(
    site, authorize, user, session, locale, resource: str, identifier: str
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "list")

    row = await target.get_object(session, identifier)

    return success_envelope(data=target.serialize_row(row, locale))


async def handle_relation_options(
    site,
    authorize,
    user,
    session,
    locale,
    resource: str,
    field: str,
    parent_values: dict,
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "list")

    options = await target.relation_options(session, field, parent_values, locale)

    return success_envelope(data=options)


async def handle_create(
    site, authorize, user, session, locale, resource: str, payload: dict, audit=None
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "create")

    row = await target.create(session, payload, locale)
    data = target.serialize_detail(row, locale)
    message = build_message(
        f"{target.name}.created", f"{target.label or target.name} created successfully."
    )

    if audit is not None:
        await audit("create", target.name, data["id"])

    return success_envelope(data=data, message=message)


async def handle_update(
    site,
    authorize,
    user,
    session,
    locale,
    resource: str,
    identifier: str,
    payload: dict,
    partial: bool,
    audit=None,
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "update")

    row = await target.update(session, identifier, payload, locale, partial=partial)
    verb = "updated"
    message = (
        build_message(
            f"{target.name}.{verb}",
            f"{target.label or target.name} {verb} successfully.",
        )
        if not partial
        else None
    )

    if audit is not None:
        await audit("update", target.name, str(identifier))

    return success_envelope(data=target.serialize_detail(row, locale), message=message)


async def handle_delete(
    site, authorize, user, session, resource: str, identifier: str, audit=None
) -> dict:
    target = site.get(resource)
    await check_permission(authorize, user, target, "delete")

    await target.delete(session, identifier)

    if audit is not None:
        await audit("delete", target.name, str(identifier))
    message = build_message(
        f"{target.name}.deleted", f"{target.label or target.name} deleted successfully."
    )

    return success_envelope(message=message)


def build_admin_router(site: AdminSite, deps: AdminDeps) -> APIRouter:
    """Build the API-first admin router as thin wrappers over the module handlers."""

    router = APIRouter()

    @router.get("/navigation")
    async def navigation(user=Depends(deps.get_current_user)):
        return await handle_navigation(site, deps.authorize, user)

    @router.get("/resources")
    async def resources(user=Depends(deps.get_current_user)):
        return success_envelope(
            data=[
                {"name": resource.name, "label": resource.label}
                for resource in site.resources()
            ]
        )

    @router.get("/resources/{resource}/schema")
    async def schema(
        resource: str,
        mode: str = "create",
        user=Depends(deps.get_current_user),
        locale=Depends(deps.get_locale),
    ):
        return await handle_schema(
            site, deps.authorize, user, resource, mode, deps.translate, locale
        )

    @router.post("/resources/{resource}/{identifier}/actions/{action}")
    async def row_action(
        resource: str,
        identifier: str,
        action: str,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_action(
            site, deps.authorize, user, session, locale, resource, action, [identifier]
        )

    @router.post("/resources/{resource}/actions/{action}")
    async def bulk_action(
        resource: str,
        action: str,
        payload: dict,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        ids = payload.get("ids", [])
        identifiers = ids if isinstance(ids, list) else []

        return await handle_action(
            site, deps.authorize, user, session, locale, resource, action, identifiers
        )

    @router.get("/resources/{resource}")
    async def grid(
        resource: str,
        request: Request,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_grid(
            site,
            deps.authorize,
            user,
            session,
            locale,
            {"resource": resource, "query": request.query_params},
        )

    @router.get("/resources/{resource}/options/{field}")
    async def relation_options(
        resource: str,
        field: str,
        request: Request,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_relation_options(
            site,
            deps.authorize,
            user,
            session,
            locale,
            resource,
            field,
            dict(request.query_params),
        )

    @router.get("/resources/{resource}/{identifier}/row")
    async def grid_row(
        resource: str,
        identifier: str,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_grid_row(
            site, deps.authorize, user, session, locale, resource, identifier
        )

    @router.get("/resources/{resource}/{identifier}")
    async def detail(
        resource: str,
        identifier: str,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_detail(
            site, deps.authorize, user, session, locale, resource, identifier
        )

    @router.post("/resources/{resource}", status_code=201)
    async def create(
        resource: str,
        payload: dict,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_create(
            site,
            deps.authorize,
            user,
            session,
            locale,
            resource,
            payload,
            audit=deps.audit,
        )

    @router.put("/resources/{resource}/{identifier}")
    async def update(
        resource: str,
        identifier: str,
        payload: dict,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_update(
            site,
            deps.authorize,
            user,
            session,
            locale,
            resource,
            identifier,
            payload,
            False,
            audit=deps.audit,
        )

    @router.patch("/resources/{resource}/{identifier}")
    async def patch(
        resource: str,
        identifier: str,
        payload: dict,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
        locale=Depends(deps.get_locale),
    ):
        return await handle_update(
            site,
            deps.authorize,
            user,
            session,
            locale,
            resource,
            identifier,
            payload,
            True,
            audit=deps.audit,
        )

    @router.delete("/resources/{resource}/{identifier}")
    async def delete(
        resource: str,
        identifier: str,
        user=Depends(deps.get_current_user),
        session=Depends(deps.get_session),
    ):
        return await handle_delete(
            site, deps.authorize, user, session, resource, identifier, audit=deps.audit
        )

    return router
