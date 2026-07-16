from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkit_admin.api import AdminDeps
from fastkit_admin.pages import build_admin_pages_router, build_page_config, render_client_json
from fastkit_admin.rendering import AdminRenderer
from fastkit_admin.site import AdminSite


def _admin_settings():
    return SimpleNamespace(path="/admin", api_path="/api")


def test_page_config_includes_client_bootstrap():
    config = build_page_config(_admin_settings(), theme={"brand_name": "Acme"}, recaptcha=SimpleNamespace(enabled=True, site_key="site-123", action="login"))

    assert config["brand_name"] == "Acme"
    assert config["recaptcha_enabled"] is True
    assert config["client"]["apiBaseUrl"] == "/api"
    assert config["client"]["recaptcha"]["siteKey"] == "site-123"


def test_render_client_json_carries_locale_and_messages():
    config = build_page_config(_admin_settings())
    client = render_client_json(config, "pt", {"grid.apply": "Aplicar"})

    assert '"locale": "pt"' in client
    assert '"grid.apply": "Aplicar"' in client


def test_render_client_json_is_safe_to_inline_in_a_script():
    config = build_page_config(_admin_settings())
    client = render_client_json(config, "pt", {"k": "</script><script>alert(1)</script>"})

    assert "</script>" not in client
    assert "\\u003c/script\\u003e" in client


def test_page_config_without_recaptcha():
    config = build_page_config(_admin_settings())

    assert config["recaptcha_enabled"] is False
    assert config["recaptcha_site_key"] == ""


class _User:
    display_name = "Root"
    profile = SimpleNamespace(avatar_asset_id="asset-1")


def _build_client(current_user, translate=None, avatar_url=None):
    site = AdminSite()

    class Ping:
        name = "ping"
        label = "Ping"
        permissions = {}

    site.register(Ping())
    site.add_group("main", "Main", order=0)
    site.add_menu("Ping", group="main", resource="ping")

    renderer = AdminRenderer()
    config = build_page_config(_admin_settings(), recaptcha=SimpleNamespace(enabled=True, site_key="k", action="login"))

    async def authorize(user, permission):
        return None

    async def optional_user(request):
        return current_user["value"]

    async def get_locale(request):
        return "pt"

    deps = AdminDeps(get_session=None, get_current_user=None, get_locale=get_locale, authorize=authorize, get_optional_user=optional_user, translate=translate)

    app = FastAPI()
    app.include_router(build_admin_pages_router(renderer, site, deps, config, avatar_url=avatar_url))

    return TestClient(app, follow_redirects=False)


def test_login_page_renders_and_includes_recaptcha():
    client = _build_client({"value": None})

    response = client.get("/admin/login")

    assert response.status_code == 200
    assert "recaptcha/api.js" in response.text


def test_shell_redirects_when_anonymous():
    client = _build_client({"value": None})

    response = client.get("/admin")

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_shell_renders_for_authenticated_user():
    holder = {"value": _User()}
    client = _build_client(holder)

    response = client.get("/admin/products")

    assert response.status_code == 200
    assert 'data-testid="sidebar"' in response.text
    assert "nav-ping" in response.text


def test_shell_renders_the_resolved_header_avatar():
    async def avatar_url(asset_id):
        return f"/media/{asset_id}.webp"

    client = _build_client({"value": _User()}, avatar_url=avatar_url)

    response = client.get("/admin/products")

    assert response.status_code == 200
    assert "/media/asset-1.webp" in response.text


def test_shell_translates_navigation_labels():
    catalog = {"Main": "Principal", "Ping": "Pingue"}

    def translate(text, locale):
        return catalog.get(text, text)

    client = _build_client({"value": _User()}, translate=translate)

    response = client.get("/admin/products")

    assert response.status_code == 200
    assert "Principal" in response.text
    assert "Pingue" in response.text
