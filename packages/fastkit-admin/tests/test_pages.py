from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from fastkit_admin.api import AdminDeps
from fastkit_admin.pages import build_admin_pages_router
from fastkit_admin.page_config import build_page_config, render_client_json
from fastkit_admin.rendering import AdminRenderer
from fastkit_admin.site import AdminSite


def _admin_settings():
    return SimpleNamespace(path="/admin", api_path="/api")


_RECAPTCHA = {
    "provider": "recaptcha",
    "enabled": True,
    "site_key": "site-123",
    "action": "login",
    "script_url": "https://www.google.com/recaptcha/api.js?render=site-123",
}


def test_page_config_includes_client_bootstrap():
    config = build_page_config(
        _admin_settings(), theme={"brand_name": "Acme"}, captcha=_RECAPTCHA
    )

    assert config["brand_name"] == "Acme"
    assert config["captcha"]["provider"] == "recaptcha"
    assert config["client"]["apiBaseUrl"] == "/api"
    assert config["client"]["captcha"]["site_key"] == "site-123"


def test_render_client_json_carries_locale_and_messages():
    config = build_page_config(_admin_settings())
    client = render_client_json(config, "pt", {"grid.apply": "Aplicar"})

    assert '"locale": "pt"' in client
    assert '"grid.apply": "Aplicar"' in client


def test_render_client_json_is_safe_to_inline_in_a_script():
    config = build_page_config(_admin_settings())
    client = render_client_json(
        config, "pt", {"k": "</script><script>alert(1)</script>"}
    )

    assert "</script>" not in client
    assert "\\u003c/script\\u003e" in client


def test_page_config_without_captcha():
    config = build_page_config(_admin_settings())

    assert config["captcha"]["provider"] is None
    assert config["captcha"]["enabled"] is False


class _User:
    display_name = "Root"
    profile = SimpleNamespace(avatar_file_id="asset-1")


def _build_client(current_user, translate=None, avatar_url=None, login=None):
    site = AdminSite()

    class Ping:
        name = "ping"
        label = "Ping"
        permissions = {}

    site.register(Ping())
    site.add_group("main", "Main", order=0)
    site.add_menu("Ping", group="main", resource="ping")

    renderer = AdminRenderer()
    config = build_page_config(_admin_settings(), captcha=_RECAPTCHA, login=login)

    async def authorize(user, permission):
        return None

    async def optional_user(request: Request):
        return current_user["value"]

    async def get_locale(request):
        return "pt"

    deps = AdminDeps(
        get_session=None,
        get_current_user=None,
        get_locale=get_locale,
        authorize=authorize,
        get_optional_user=optional_user,
        translate=translate,
    )

    app = FastAPI()
    app.include_router(
        build_admin_pages_router(renderer, site, deps, config, avatar_url=avatar_url)
    )

    return TestClient(app, follow_redirects=False)


def test_login_page_renders_and_includes_recaptcha():
    client = _build_client({"value": None})

    response = client.get("/admin/login")

    assert response.status_code == 200
    assert "recaptcha/api.js" in response.text


def test_page_config_login_defaults_and_custom():
    default = build_page_config(_admin_settings())
    assert default["login"]["identifier_type"] == "email"
    assert default["login"]["password"] is True
    assert default["client"]["login"]["identifierType"] == "email"

    custom = build_page_config(
        _admin_settings(), login={"identifier_type": "username", "password": False}
    )
    assert custom["login"]["identifier_type"] == "username"
    assert custom["login"]["password"] is False


def test_login_page_renders_declarative_selector_and_oauth():
    login = {
        "identifier": {
            "label": "login.username",
            "type": "text",
            "autocomplete": "username",
            "default": "",
        },
        "identifier_type": "username",
        "identifier_types": [
            {"value": "email", "label": "Email"},
            {"value": "phone", "label": "Phone"},
        ],
        "oauth": [
            {
                "name": "google",
                "label": "Continue with Google",
                "url": "/oauth/google",
                "icon": "brand-google",
            }
        ],
    }
    client = _build_client({"value": None}, login=login)

    response = client.get("/admin/login")

    assert response.status_code == 200
    assert 'data-testid="login-identifier-type"' in response.text
    assert 'data-testid="login-oauth-google"' in response.text
    assert 'href="/oauth/google"' in response.text
    assert 'type="text"' in response.text


def test_shell_redirects_when_anonymous():
    client = _build_client({"value": None})

    response = client.get("/admin")

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_shell_renders_for_authenticated_user():
    holder = {"value": _User()}
    client = _build_client(holder)

    response = client.get("/admin")

    assert response.status_code == 200
    assert 'data-testid="sidebar"' in response.text
    assert "nav-ping" in response.text


def test_shell_renders_the_resolved_header_avatar():
    async def avatar_url(asset_id):
        return f"/media/{asset_id}.webp"

    client = _build_client({"value": _User()}, avatar_url=avatar_url)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "/media/asset-1.webp" in response.text


def test_shell_translates_navigation_labels():
    catalog = {"Main": "Principal", "Ping": "Pingue"}

    def translate(text, locale):
        return catalog.get(text, text)

    client = _build_client({"value": _User()}, translate=translate)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Principal" in response.text
    assert "Pingue" in response.text
