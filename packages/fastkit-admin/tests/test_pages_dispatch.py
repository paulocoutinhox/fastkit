from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.responses import RedirectResponse
from starlette.datastructures import QueryParams

from fastkit_core.errors.exceptions import AuthorizationError, NotFoundError
from fastkit_core.errors.codes import AUTHORIZATION_DENIED
from fastkit_admin.pages import PagesDeps, dispatch_screen, render_login, render_screen
from fastkit_admin.page_config import build_page_config
from fastkit_admin.rendering import AdminRenderer

_USER = SimpleNamespace(id="u1", display_name="Root", email="root@x.com", profile=None, timezone="UTC")


async def _seed(session, model, count=3):
    for index in range(count):
        session.add(model(name=f"Product {index}", price=Decimal("1.00"), category="general", is_active=True))

    await session.commit()


async def _report_data(name, session, locale, params, check):
    if not await check("reports.view"):
        raise AuthorizationError(AUTHORIZATION_DENIED, message="denied")

    return {"title": "Sales", "columns": [{"key": "c", "label": "C", "align": "left"}], "rows": [{"c": "x"}], "formats": ["csv"], "filters": []}


async def _profile_data(user, locale):
    return {"display_name": "Root", "email": "root@x.com", "first_name": "", "last_name": "", "avatar_url": None, "identifier_types": ["email"], "identifiers": []}


def _pages(site, authorize=None, translate=None, report_data=_report_data, profile_data=_profile_data):
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    deps = SimpleNamespace(authorize=authorize, translate=translate, translator=None)

    return PagesDeps(AdminRenderer(), site, deps, config, None, None, report_data, profile_data)


def _body(response):
    return response.body.decode()


async def test_dispatch_dashboard(site):
    response = await dispatch_screen(_pages(site), "", QueryParams(""), _USER, None, "en")

    assert 'data-testid="dashboard"' in _body(response)


async def test_dispatch_list_and_fragment(session, product_model, site):
    await _seed(session, product_model, 3)
    pages = _pages(site)

    full = await dispatch_screen(pages, "products", QueryParams(""), _USER, session, "en")
    assert 'data-testid="grid"' in _body(full)
    assert 'data-testid="sidebar"' in _body(full)

    fragment = await dispatch_screen(pages, "products", QueryParams("_fragment=table"), _USER, session, "en")
    assert 'data-testid="grid-row-' in _body(fragment)
    assert 'data-testid="sidebar"' not in _body(fragment)


async def test_dispatch_form_create_and_edit(session, product_model, site):
    await _seed(session, product_model, 1)
    pages = _pages(site)

    create = await dispatch_screen(pages, "products/new", QueryParams(""), _USER, session, "en")
    assert 'data-testid="form"' in _body(create)
    assert 'data-testid="field-name"' in _body(create)

    edit = await dispatch_screen(pages, "products/1/edit", QueryParams(""), _USER, session, "en")
    assert 'data-record-id="1"' in _body(edit)


async def test_dispatch_form_fragment_renders_related_widget(session, product_model, tag_model):
    from fastkit_admin.fields import RelationField, TextField
    from fastkit_admin.resource import AdminResource
    from fastkit_admin.site import AdminSite

    class Owners(AdminResource):
        name = "owners"
        model = tag_model
        list_columns = ["slug"]
        form_fields = [TextField("slug")]
        permissions = {}

    class Things(AdminResource):
        name = "things"
        model = product_model
        list_columns = ["name"]
        form_fields = [TextField("name"), RelationField("owner_id", related="owners")]
        permissions = {}

    local = AdminSite()
    local.register(Owners())
    local.register(Things())

    fragment = await dispatch_screen(_pages(local), "things/new", QueryParams("_fragment=form"), _USER, session, "en")
    body = _body(fragment)

    assert 'data-testid="form"' in body
    assert 'data-testid="sidebar"' not in body
    assert 'data-related="owners"' in body
    assert 'data-testid="related-add-owner_id"' in body
    assert 'data-testid="related-edit-owner_id"' in body


async def test_dispatch_detail(session, product_model, site):
    await _seed(session, product_model, 1)

    response = await dispatch_screen(_pages(site), "products/1", QueryParams(""), _USER, session, "en")

    assert 'data-testid="detail-name"' in _body(response)


async def test_dispatch_report_full_and_fragment(site):
    pages = _pages(site)

    full = await dispatch_screen(pages, "reports/sales", QueryParams(""), _USER, None, "en")
    assert 'data-testid="report-table"' in _body(full)
    assert 'data-testid="sidebar"' in _body(full)

    fragment = await dispatch_screen(pages, "reports/sales", QueryParams("_fragment=table"), _USER, None, "en")
    assert 'data-testid="report-table"' in _body(fragment)
    assert 'data-testid="sidebar"' not in _body(fragment)


async def test_dispatch_report_without_provider_is_not_found(site):
    with pytest.raises(NotFoundError):
        await dispatch_screen(_pages(site, report_data=None), "reports/sales", QueryParams(""), _USER, None, "en")


async def test_dispatch_report_enforces_permission(site):
    async def deny(user, permission):
        raise AuthorizationError(AUTHORIZATION_DENIED, message="denied")

    response = await dispatch_screen(_pages(site, authorize=deny), "reports/sales", QueryParams(""), _USER, None, "en")

    assert response.status_code == 403
    assert 'data-testid="content-error"' in _body(response)


async def test_dispatch_profile(site):
    response = await dispatch_screen(_pages(site), "profile", QueryParams(""), _USER, None, "en")

    assert 'data-testid="profile"' in _body(response)


async def test_dispatch_profile_without_provider(site):
    response = await dispatch_screen(_pages(site, profile_data=None), "profile", QueryParams(""), _USER, None, "en")

    assert 'data-testid="profile"' in _body(response)


async def test_dispatch_notfound(site):
    with pytest.raises(NotFoundError):
        await dispatch_screen(_pages(site), "a/b/c/d", QueryParams(""), _USER, None, "en")


async def test_dispatch_enforces_permissions(session, product_model, site):
    async def deny(user, permission):
        raise AuthorizationError(AUTHORIZATION_DENIED, message="denied")

    response = await dispatch_screen(_pages(site, authorize=deny), "products", QueryParams(""), _USER, session, "en")

    assert response.status_code == 403
    assert 'data-testid="content-error"' in _body(response)


async def test_dispatch_translates_navigation(session, product_model, site):
    def translate(text, locale):
        return {"Catalog": "Catalogo", "Products": "Produtos"}.get(text, text)

    await _seed(session, product_model, 1)

    response = await dispatch_screen(_pages(site, translate=translate), "products", QueryParams(""), _USER, session, "en")

    assert "Catalogo" in _body(response)


class _Request:
    def __init__(self, query=""):
        self.query_params = QueryParams(query)


async def test_render_login():
    site = None
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    deps = SimpleNamespace(get_locale=_locale, translator=None)
    pages = PagesDeps(AdminRenderer(), site, deps, config, None, None, None, None)

    response = await render_login(pages, _Request())

    assert 'data-testid="login-form"' in _body(response)


async def _locale(request):
    return "en"


async def test_render_screen_redirects_anonymous(site):
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    deps = SimpleNamespace(get_locale=_locale, authorize=None, translate=None, translator=None)
    pages = PagesDeps(AdminRenderer(), site, deps, config, None, None, _report_data, _profile_data)

    response = await render_screen(pages, _Request(), "products", None, None)

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 303


async def test_render_screen_dispatches_for_user(site):
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    deps = SimpleNamespace(get_locale=_locale, authorize=None, translate=None, translator=None)
    pages = PagesDeps(AdminRenderer(), site, deps, config, None, None, _report_data, _profile_data)

    response = await render_screen(pages, _Request(), "", _USER, None)

    assert 'data-testid="dashboard"' in _body(response)


class _Translator:
    def gettext(self, key, locale=None, **params):
        return f"T:{key}"

    def messages(self, locale):
        return {"grid.new": "New"}


async def test_dispatch_uses_translator(site):
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    deps = SimpleNamespace(authorize=None, translate=None, translator=None)
    pages = PagesDeps(AdminRenderer(), site, deps, config, _Translator(), None, _report_data, _profile_data)

    response = await dispatch_screen(pages, "", QueryParams(""), _USER, None, "en")

    assert response.status_code == 200


def test_sub_page_route_is_wired(site):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from fastkit_admin.pages import build_admin_pages_router

    async def get_session():
        yield None

    async def get_optional_user(request: Request):
        return _USER

    async def get_locale(request: Request):
        return "en"

    deps = SimpleNamespace(get_session=get_session, get_optional_user=get_optional_user, get_locale=get_locale, authorize=None, translate=None, translator=None)
    config = build_page_config(SimpleNamespace(path="/admin", api_path="/api"))
    app = FastAPI()
    app.include_router(build_admin_pages_router(AdminRenderer(), site, deps, config, report_data=_report_data, profile_data=_profile_data))

    response = TestClient(app).get("/admin/profile")

    assert response.status_code == 200
    assert 'data-testid="profile"' in response.text
