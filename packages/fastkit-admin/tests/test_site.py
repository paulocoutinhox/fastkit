from fastkit_admin.site import AdminSite


async def _allow_all(permission):
    return True


async def _deny(permission):
    return False


async def test_navigation_public_menu_always_visible():
    site = AdminSite()
    site.add_group("main", "Main", order=0)
    site.add_menu("Dashboard", group="main", path="/dashboard", icon="home")

    groups = await site.navigation(_deny)

    assert groups[0]["items"][0]["label"] == "Dashboard"
    assert groups[0]["items"][0]["icon"] == "home"


async def test_menu_icon_defaults_to_resource_icon():
    site = AdminSite()

    class Res:
        name = "widgets"
        icon = "box"
        permissions = {}

    site.register(Res())
    site.add_group("main", "Main")
    site.add_menu("Widgets", group="main", resource="widgets")
    site.add_menu("Loose", group="main", path="/loose")

    groups = await site.navigation(_allow_all)
    icons = {item["label"]: item["icon"] for item in groups[0]["items"]}

    assert icons["Widgets"] == "box"
    assert icons["Loose"] == "point"


async def test_navigation_group_without_definition_uses_key():
    site = AdminSite()
    site.add_menu("Loose", group="ungrouped", path="/x")

    groups = await site.navigation(_allow_all)

    assert groups[0]["key"] == "ungrouped"
    assert groups[0]["label"] == "Ungrouped"


async def test_navigation_tolerates_a_menu_for_an_unregistered_resource():
    site = AdminSite()
    site.add_menu("Orders", group="main", resource="orders")

    groups = await site.navigation(_allow_all)

    assert groups[0]["items"][0]["label"] == "Orders"


async def test_navigation_orders_groups():
    site = AdminSite()
    site.add_group("second", "Second", order=2)
    site.add_group("first", "First", order=1)
    site.add_menu("A", group="second", path="/a")
    site.add_menu("B", group="first", path="/b")

    groups = await site.navigation(_allow_all)

    assert [group["key"] for group in groups] == ["first", "second"]


async def test_navigation_hides_denied_permission_menu():
    site = AdminSite()
    site.add_menu("Secret", group="g", path="/s", permission="secret.view")

    assert await site.navigation(_deny) == []
