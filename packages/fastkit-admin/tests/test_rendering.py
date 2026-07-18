from fastkit_admin.rendering import AdminRenderer


def test_renders_package_template():
    renderer = AdminRenderer()

    html = renderer.render(
        "admin/login.html",
        t=lambda key, **params: key,
        config={
            "brand_name": "FastKit",
            "favicon": "x",
            "head_assets": [],
            "body_assets": [],
            "static_base": "/admin-static",
            "primary_color": "#000",
            "primary_color_hover": "#111",
            "captcha": {"provider": None},
            "login": {
                "identifier": {
                    "label": "login.email",
                    "type": "email",
                    "autocomplete": "username",
                    "default": "",
                },
                "identifier_types": [],
                "password": True,
                "oauth": [],
            },
            "client_json": "{}",
        },
    )

    assert "Sign in" in html
    assert 'autocomplete="new-password"' in html


def test_consumer_directory_overrides_package(tmp_path):
    override = tmp_path / "admin"
    override.mkdir()
    (override / "_extra_head.html").write_text(
        "<meta name='marker' content='overridden'>"
    )

    renderer = AdminRenderer(override_dirs=[str(tmp_path)])
    html = renderer.render(
        "admin/base.html",
        config={
            "brand_name": "FastKit",
            "favicon": "x",
            "head_assets": [],
            "body_assets": [],
            "static_base": "/s",
            "primary_color": "#000",
            "primary_color_hover": "#111",
            "captcha": {"provider": None},
            "client_json": "{}",
        },
    )

    assert "overridden" in html
