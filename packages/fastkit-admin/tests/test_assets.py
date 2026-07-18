from types import SimpleNamespace

from fastapi import FastAPI

from fastkit_admin.assets import AssetRegistry
from fastkit_admin.mounting import mount_admin_static, mount_assets


def _provider(mount, assets, static_dir="/tmp"):
    return SimpleNamespace(MOUNT=mount, STATIC_DIR=static_dir, ASSETS=assets)


def test_registry_orders_and_filters_by_kind():
    registry = AssetRegistry(
        [
            _provider(
                "/vendor/a",
                [
                    {"name": "a-js", "kind": "js", "path": "a.js", "order": 30},
                    {"name": "a-css", "kind": "css", "path": "a.css", "order": 20},
                ],
            ),
            _provider(
                "/vendor/b",
                [
                    {"name": "b-css", "kind": "css", "path": "b.css", "order": 10},
                    {
                        "name": "b-js",
                        "kind": "js",
                        "path": "b.js",
                        "order": 5,
                        "attrs": {"referrerpolicy": "origin"},
                    },
                ],
            ),
        ]
    )

    css = registry.tags("css")
    js = registry.tags("js")

    assert [tag.url for tag in css] == ["/vendor/b/b.css", "/vendor/a/a.css"]
    assert [tag.url for tag in js] == ["/vendor/b/b.js", "/vendor/a/a.js"]
    assert js[0].attrs == {"referrerpolicy": "origin"}
    assert css[0].attrs == {}


def test_registry_default_order_is_stable():
    registry = AssetRegistry(
        [_provider("/vendor/a", [{"name": "x", "kind": "js", "path": "x.js"}])]
    )

    assert registry.tags("js")[0].url == "/vendor/a/x.js"


def test_registry_mounts():
    registry = AssetRegistry([_provider("/vendor/a", [], static_dir="/dir/a")])

    assert registry.mounts() == [("/vendor/a", "/dir/a")]


def test_discover_finds_installed_vendor_packages():
    registry = AssetRegistry.discover()
    js_urls = {tag.url for tag in registry.tags("js")}
    css_urls = {tag.url for tag in registry.tags("css")}

    assert "/vendor/jquery/jquery.min.js" in js_urls
    assert "/vendor/tinymce/tinymce/tinymce.min.js" in js_urls
    assert "/vendor/tabler/tabler.min.css" in css_urls


def test_mount_assets_mounts_every_provider(tmp_path):
    app = FastAPI()
    registry = AssetRegistry([_provider("/vendor/a", [], static_dir=str(tmp_path))])
    mount_assets(app, registry)

    assert any(getattr(route, "path", None) == "/vendor/a" for route in app.routes)


def test_mount_admin_static_mounts_client_and_assets(tmp_path):
    app = FastAPI()
    registry = AssetRegistry([_provider("/vendor/a", [], static_dir=str(tmp_path))])
    mount_admin_static(app, static_base="/assets", registry=registry)

    paths = {getattr(route, "path", None) for route in app.routes}

    assert "/assets" in paths
    assert "/vendor/a" in paths
