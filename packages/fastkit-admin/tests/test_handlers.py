import pytest

from fastkit_core.errors.exceptions import AuthorizationError, NotFoundError
from fastkit_admin.api import (
    check_permission,
    handle_create,
    handle_delete,
    handle_detail,
    handle_grid,
    handle_grid_row,
    handle_relation_options,
    handle_update,
)


class DenyingUser:
    id = "u"
    is_root = False
    is_active = True


async def _authorize_allow(user, permission):
    return None


async def _authorize_deny(user, permission):
    from fastkit_core.errors.codes import AUTHORIZATION_DENIED

    raise AuthorizationError(
        AUTHORIZATION_DENIED, message=f"permission '{permission}' is required"
    )


class Params:
    def __init__(self, items):
        self._items = items

    def multi_items(self):
        return self._items

    def get(self, key, default=None):
        for name, value in self._items:
            if name == key:
                return value

        return default


async def test_check_permission_allow_and_skip():
    class Resource:
        permissions = {"list": "products.view"}

    await check_permission(_authorize_allow, DenyingUser(), Resource(), "list")
    await check_permission(None, DenyingUser(), Resource(), "list")

    class Open:
        permissions = {}

    await check_permission(_authorize_allow, DenyingUser(), Open(), "list")


async def test_check_permission_denies():
    class Resource:
        permissions = {"create": "products.create"}

    with pytest.raises(AuthorizationError):
        await check_permission(_authorize_deny, DenyingUser(), Resource(), "create")


async def test_handle_create_grid_detail_update_delete(session, site):
    user = DenyingUser()

    created = await handle_create(
        site,
        _authorize_allow,
        user,
        session,
        "pt",
        "products",
        {
            "name": "Widget",
            "price": "1.234,50",
            "category": "general",
            "is_active": "true",
        },
    )
    assert created["message"]["code"] == "products.created"
    identifier = created["data"]["id"]

    grid = await handle_grid(
        site,
        _authorize_allow,
        user,
        session,
        "en",
        {"resource": "products", "query": Params([("sort", "name")])},
    )
    assert grid["meta"]["pagination"]["total_items"] == 1

    detail = await handle_detail(
        site, _authorize_allow, user, session, "en", "products", identifier
    )
    assert detail["data"]["name"] == "Widget"

    updated = await handle_update(
        site,
        _authorize_allow,
        user,
        session,
        "en",
        "products",
        identifier,
        {
            "name": "Renamed",
            "price": "9.99",
            "category": "premium",
            "is_active": "false",
        },
        False,
    )
    assert updated["message"]["code"] == "products.updated"

    patched = await handle_update(
        site,
        _authorize_allow,
        user,
        session,
        "en",
        "products",
        identifier,
        {"name": "Patched"},
        True,
    )
    assert patched["message"] is None
    assert patched["data"]["name"] == "Patched"

    deleted = await handle_delete(
        site, _authorize_allow, user, session, "products", identifier
    )
    assert deleted["message"]["code"] == "products.deleted"


async def test_handlers_record_audit(session, site):
    events = []

    async def audit(action, resource, resource_id):
        events.append((action, resource, resource_id))

    created = await handle_create(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "en",
        "products",
        {
            "name": "Audited",
            "price": "1.00",
            "category": "general",
            "is_active": "true",
        },
        audit=audit,
    )
    identifier = created["data"]["id"]

    await handle_update(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "en",
        "products",
        identifier,
        {"name": "Renamed"},
        True,
        audit=audit,
    )
    await handle_delete(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "products",
        identifier,
        audit=audit,
    )

    assert [event[0] for event in events] == ["create", "update", "delete"]
    assert all(event[1] == "products" for event in events)


async def test_handle_grid_row(session, site):
    created = await handle_create(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "en",
        "products",
        {"name": "Solo", "price": "3.00", "category": "general", "is_active": "true"},
    )
    identifier = created["data"]["id"]

    row = await handle_grid_row(
        site, _authorize_allow, DenyingUser(), session, "en", "products", identifier
    )

    assert row["data"]["name"] == "Solo"
    assert row["data"]["id"] == str(identifier)


async def test_handle_relation_options(session, site):
    empty = await handle_relation_options(
        site, _authorize_allow, DenyingUser(), session, "en", "products", "owner_id", {}
    )
    assert empty["data"] == []

    filtered = await handle_relation_options(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "en",
        "products",
        "owner_id",
        {"category": "premium"},
    )
    assert filtered["data"] == [{"value": 1, "label": "premium owner"}]


async def test_handle_detail_missing(session, site):
    import uuid

    with pytest.raises(NotFoundError):
        await handle_detail(
            site,
            _authorize_allow,
            DenyingUser(),
            session,
            "en",
            "products",
            str(uuid.uuid4()),
        )


async def test_handle_create_denied(session, site):
    with pytest.raises(AuthorizationError):
        await handle_create(
            site,
            _authorize_deny,
            DenyingUser(),
            session,
            "en",
            "products",
            {"name": "X", "price": "1.00"},
        )


async def test_handle_action_direct(session, site):
    from fastkit_admin.api import handle_action

    user = DenyingUser()
    created = await handle_create(
        site,
        _authorize_allow,
        user,
        session,
        "en",
        "products",
        {"name": "Act", "price": "5.00", "is_active": "true"},
    )
    identifier = created["data"]["id"]

    result = await handle_action(
        site,
        _authorize_allow,
        user,
        session,
        "en",
        "products",
        "deactivate",
        [identifier],
    )

    assert result["data"]["deactivated"] == 1
    assert result["message"]["code"] == "products.deactivate"


async def test_handle_navigation_and_schema_direct(site):
    from fastkit_admin.api import handle_navigation, handle_schema

    nav = await handle_navigation(site, _authorize_allow, DenyingUser())
    assert any(group["key"] == "catalog" for group in nav["data"])

    schema = await handle_schema(
        site, _authorize_allow, DenyingUser(), "products", "create"
    )
    assert schema["data"]["grid"]["flags"]["can_create"] is True


async def test_handle_action_permissioned_without_authorize_runs(session, site):
    from fastkit_admin.api import handle_action

    created = await handle_create(
        site,
        _authorize_allow,
        DenyingUser(),
        session,
        "en",
        "products",
        {"name": "NoAuth", "price": "3.00", "is_active": "true"},
    )

    result = await handle_action(
        site,
        None,
        DenyingUser(),
        session,
        "en",
        "products",
        "deactivate",
        [created["data"]["id"]],
    )

    assert result["data"]["deactivated"] == 1


async def test_handle_action_without_permission_requires_update(session, site):
    from fastkit_admin.api import handle_action

    with pytest.raises(AuthorizationError):
        await handle_action(
            site,
            _authorize_deny,
            DenyingUser(),
            session,
            "en",
            "products",
            "touch",
            [],
        )
