from decimal import Decimal

import pytest

from fastkit_core.errors.exceptions import NotFoundError, ValidationError
from fastkit_admin.resource import GridQuery


async def _seed(session, model, count=3):
    for index in range(count):
        session.add(model(name=f"Item {index}", price=Decimal(f"{index}.50"), category="premium" if index else "general", is_active=index % 2 == 0))

    await session.commit()


async def test_grid_serialization_with_custom_column(session, product_admin, product_model):
    admin = product_admin
    await _seed(session, product_model, 1)

    result = await admin.list(session, GridQuery(), "pt")
    row = result["rows"][0]

    assert row["price"] == "0.50"
    assert row["is_active"] is True
    assert 'class="badge' in row["badge"]
    assert result["pagination"]["total_items"] == 1


async def test_grid_search(session, product_admin, product_model):
    admin = product_admin
    await _seed(session, product_model, 3)

    result = await admin.list(session, GridQuery(search="Item 1"), "en")

    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "Item 1"


async def test_grid_filters(session, product_admin, product_model):
    admin = product_admin
    await _seed(session, product_model, 4)

    active = await admin.list(session, GridQuery(filters={"is_active": "true"}), "en")
    assert all(row["is_active"] for row in active["rows"])

    premium = await admin.list(session, GridQuery(filters={"category": "premium"}), "en")
    assert all(row["category"] == "premium" for row in premium["rows"])

    unknown = await admin.list(session, GridQuery(filters={"not_registered": "x"}), "en")
    assert unknown["pagination"]["total_items"] == 4


async def test_grid_sort_and_pagination(session, product_admin, product_model):
    admin = product_admin
    await _seed(session, product_model, 5)

    page1 = await admin.list(session, GridQuery(page=1, page_size=2, sort="name"), "en")
    assert len(page1["rows"]) == 2
    assert page1["pagination"]["total_pages"] == 3

    # invalid sort field falls back to default ordering
    fallback = await admin.list(session, GridQuery(sort="; DROP TABLE"), "en")
    assert fallback["pagination"]["total_items"] == 5


async def test_create_parses_localized_decimal(session, product_admin, product_model):
    admin = product_admin

    row = await admin.create(session, {"name": "Widget", "price": "1.234,50", "category": "general", "is_active": "true"}, "pt")

    assert row.price == Decimal("1234.50")
    assert row.is_active is True


async def test_create_validation_error(session, product_admin, product_model):
    admin = product_admin

    with pytest.raises(ValidationError):
        await admin.create(session, {"name": "", "price": "10"}, "en")


async def test_update_partial(session, product_admin, product_model):
    admin = product_admin
    row = await admin.create(session, {"name": "Widget", "price": "10.00"}, "en")

    updated = await admin.update(session, row.id, {"name": "Renamed"}, "en", partial=True)

    assert updated.name == "Renamed"
    assert updated.price == Decimal("10.00")


async def test_get_object_missing_raises(session, product_admin, product_model):
    admin = product_admin

    with pytest.raises(NotFoundError):
        await admin.get_object(session, 999999)


async def test_delete(session, product_admin, product_model):
    admin = product_admin
    row = await admin.create(session, {"name": "Widget", "price": "10.00"}, "en")

    await admin.delete(session, row.id)

    result = await admin.list(session, GridQuery(), "en")
    assert result["rows"] == []


async def test_detail_serialization(session, product_admin, product_model):
    admin = product_admin
    row = await admin.create(session, {"name": "Widget", "price": "10.50", "category": "premium"}, "en")

    detail = admin.serialize_detail(row, "pt")

    assert detail["price"] == "10,50"
    assert detail["category"] == "premium"


def test_schemas(product_admin):
    admin = product_admin
    grid = admin.grid_schema()
    form = admin.form_schema("create")

    form_fields = [field for fieldset in form["fieldsets"] for field in fieldset["fields"]]

    assert grid["resource"] == "products"
    assert {column["name"] for column in grid["columns"]} == {"name", "price", "category", "is_active", "badge", "created_at"}
    assert any(item["type"] == "choice" for item in grid["filters"])
    assert form_fields[0]["name"] == "name"
    assert "updated_at" not in {field["name"] for field in form_fields}
    assert form["actions"][0]["name"] == "save"


def test_schemas_translate_display_strings():
    from fastkit_admin.actions import AdminAction
    from fastkit_admin.fields import BooleanField, TextField
    from fastkit_admin.filters import TextFilter
    from fastkit_admin.resource import AdminResource, Fieldset

    class DemoAdmin(AdminResource):
        name = "demo"
        label = "Products"
        list_columns = ["name"]
        form_fields = [TextField("name", label="Name"), BooleanField("active", label="Active")]
        fieldsets = [Fieldset("Identity", ["name", "active"], description="Who")]
        filters = [TextFilter("name", label="Name")]
        actions = [AdminAction(name="go", label="Deactivate", scope="bulk")]

    catalog = {"Products": "Produtos", "Name": "Nome", "Active": "Ativo", "Identity": "Identidade", "Who": "Quem", "Deactivate": "Desativar", "Save": "Salvar"}

    def translate(text):
        return catalog.get(text, text)

    grid = DemoAdmin().grid_schema(translate=translate)
    form = DemoAdmin().form_schema("create", translate=translate)

    assert grid["label"] == "Produtos"
    assert grid["columns"][0]["label"] == "Nome"
    assert grid["columns"][0]["name"] == "name"
    assert grid["filters"][0]["label"] == "Nome"
    assert grid["actions"][0]["label"] == "Desativar"
    assert form["fieldsets"][0]["title"] == "Identidade"
    assert form["fieldsets"][0]["description"] == "Quem"
    assert form["fieldsets"][0]["fields"][0]["label"] == "Nome"
    assert form["actions"][0]["label"] == "Salvar"


def test_form_schema_with_explicit_fieldsets():
    from fastkit_admin.fields import BooleanField, TextField
    from fastkit_admin.resource import AdminResource, Fieldset

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), TextField("email"), BooleanField("active")]
        fieldsets = [Fieldset("Identity", ["name", "email"]), Fieldset("Flags", ["active"], description="Toggles")]

    form = DemoAdmin().form_schema("create")

    assert [fieldset["title"] for fieldset in form["fieldsets"]] == ["Identity", "Flags"]
    assert [field["name"] for field in form["fieldsets"][0]["fields"]] == ["name", "email"]
    assert form["fieldsets"][1]["description"] == "Toggles"


def test_form_schema_drops_empty_fieldsets_on_create():
    from fastkit_admin.fields import DateTimeField, TextField
    from fastkit_admin.resource import AdminResource, Fieldset

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), DateTimeField("created_at", readonly=True)]
        fieldsets = [Fieldset("Main", ["name"]), Fieldset("Record", ["created_at"])]

    create_titles = [fieldset["title"] for fieldset in DemoAdmin().form_schema("create")["fieldsets"]]
    edit_titles = [fieldset["title"] for fieldset in DemoAdmin().form_schema("edit")["fieldsets"]]

    assert create_titles == ["Main"]
    assert edit_titles == ["Main", "Record"]


def test_serialize_detail_applies_render_override():
    from fastkit_admin.fields import BooleanField, TextField
    from fastkit_admin.resource import AdminResource

    class Row:
        id = "1"
        name = "Ada"
        is_active = True

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), BooleanField("is_active")]

        def render_is_active(self, row, locale):
            return "<span class='badge'>on</span>" if row.is_active else "<span class='badge'>off</span>"

    detail = DemoAdmin().serialize_detail(Row(), "en")

    assert detail["_html"]["is_active"] == "<span class='badge'>on</span>"
    assert "name" not in detail["_html"]


def test_serialize_detail_skips_write_only():
    from fastkit_admin.fields import PasswordField, TextField
    from fastkit_admin.resource import AdminResource

    class Row:
        id = "1"
        name = "Ada"
        secret = "hidden"

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), PasswordField("secret")]

    detail = DemoAdmin().serialize_detail(Row(), "en")

    assert detail["name"] == "Ada"
    assert "secret" not in detail


def test_default_ordering_falls_back_to_primary_key():
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class ByDefault(AdminResource):
        name = "demo"
        list_columns = ["name"]
        form_fields = [TextField("name")]

    class ByCode(AdminResource):
        name = "demo"
        pk_field = "code"
        ordering = ["-name"]
        list_columns = ["name"]
        form_fields = [TextField("name")]

    assert ByDefault().grid_schema()["default_sort"] == ["-id"]
    assert ByCode()._default_ordering() == ["-name"]


def test_grid_columns_carry_field_type():
    from fastkit_admin.fields import BooleanField, TextField
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"
        list_columns = ["name", "active", "code"]
        form_fields = [TextField("name"), BooleanField("active")]

    columns = {column["name"]: column for column in DemoAdmin().grid_schema()["columns"]}

    assert columns["active"]["field_type"] == "boolean"
    assert columns["name"]["field_type"] == "text"
    assert columns["code"]["field_type"] == "text"


def test_grid_schema_exposes_select_all_and_defaults_every_column_clickable():
    from fastkit_admin.columns import Column
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"
        select_all = False
        list_columns = [Column("name"), "code"]
        form_fields = [TextField("name")]

    grid = DemoAdmin().grid_schema()
    columns = {column["name"]: column for column in grid["columns"]}

    assert grid["select_all"] is False
    assert columns["name"]["clickable"] is True
    assert columns["code"]["clickable"] is True


def test_clickable_columns_restricts_or_disables_click_through():
    from fastkit_admin.resource import AdminResource

    class SubsetAdmin(AdminResource):
        name = "subset"
        list_columns = ["name", "code"]
        clickable_columns = ["name"]

    class NoneAdmin(AdminResource):
        name = "none"
        list_columns = ["name", "code"]
        clickable_columns = []

    subset = {column["name"]: column for column in SubsetAdmin().grid_schema()["columns"]}
    assert subset["name"]["clickable"] is True
    assert subset["code"]["clickable"] is False

    disabled = {column["name"]: column for column in NoneAdmin().grid_schema()["columns"]}
    assert disabled["name"]["clickable"] is False
    assert disabled["code"]["clickable"] is False


async def test_sort_override_is_used(session, product_model):
    from sqlalchemy import func

    from fastkit_admin.columns import Column
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource, GridQuery

    class ByNameLength(AdminResource):
        name = "products"
        model = product_model
        list_columns = ["name", Column("name_length")]
        form_fields = [TextField("name")]
        ordering = ["-created_at"]

        def sort_name_length(self):
            return func.length(product_model.name)

    admin = ByNameLength()
    session.add_all([product_model(name="zzzz", price=1), product_model(name="a", price=1)])
    await session.commit()

    result = await admin.list(session, GridQuery(sort="name_length"), "en")

    assert [row["name"] for row in result["rows"]] == ["a", "zzzz"]


async def test_read_only_resource_blocks_writes(session, product_model):
    from fastkit_core.errors.exceptions import AuthorizationError
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class LogAdmin(AdminResource):
        name = "logs"
        model = product_model
        read_only = True
        list_columns = ["name"]
        form_fields = [TextField("name")]

    admin = LogAdmin()
    row = product_model(name="entry", price=1)
    session.add(row)
    await session.commit()

    with pytest.raises(AuthorizationError):
        await admin.create(session, {"name": "x"}, "en")
    with pytest.raises(AuthorizationError):
        await admin.update(session, row.id, {"name": "x"}, "en")
    with pytest.raises(AuthorizationError):
        await admin.delete(session, row.id)

    async def allow(permission):
        return True

    flags = await admin.permission_flags(allow)
    assert flags["can_list"] is True
    assert flags["can_create"] is False
    assert flags["can_update"] is False
    assert flags["can_delete"] is False


async def test_custom_pk_field_drives_id_and_lookup(session, product_model):
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class ByName(AdminResource):
        name = "products"
        model = product_model
        pk_field = "name"
        list_columns = ["name"]
        form_fields = [TextField("name")]

    admin = ByName()
    session.add(product_model(name="Widget", price=1))
    session.add(product_model(name="123", price=2))
    await session.commit()

    fetched = await admin.get_object(session, "Widget")
    assert admin.serialize_row(fetched)["id"] == "Widget"

    numeric_name = await admin.get_object(session, "123")
    assert admin.serialize_row(numeric_name)["id"] == "123"


async def test_delete_removes_owned_files(session, product_model):
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class RecordingStorage:
        def __init__(self):
            self.deleted = []

        async def delete(self, key):
            self.deleted.append(key)

    class FailingStorage:
        async def delete(self, key):
            raise RuntimeError("storage down")

    storage = RecordingStorage()

    class DemoAdmin(AdminResource):
        name = "products"
        model = product_model
        file_fields = ["name"]
        media_base_url = "/media"
        form_fields = [TextField("name")]

    admin = DemoAdmin()
    admin.storage = storage

    row = product_model(name="/media/covers/a.png", price=1)
    session.add(row)
    await session.commit()

    await admin.delete(session, row.id)
    assert storage.deleted == ["covers/a.png"]

    # a storage failure never blocks the delete
    admin.storage = FailingStorage()
    other = product_model(name="/media/covers/b.png", price=1)
    session.add(other)
    await session.commit()
    await admin.delete(session, other.id)

    # an external URL is left untouched (no storage call)
    admin.storage = RecordingStorage()
    external = product_model(name="https://cdn.example.com/x.png", price=1)
    session.add(external)
    await session.commit()
    await admin.delete(session, external.id)
    assert admin.storage.deleted == []


async def test_update_removes_a_replaced_file(session, product_model):
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource

    class RecordingStorage:
        def __init__(self):
            self.deleted = []

        async def delete(self, key):
            self.deleted.append(key)

    storage = RecordingStorage()

    class DemoAdmin(AdminResource):
        name = "products"
        model = product_model
        file_fields = ["name"]
        media_base_url = "/media"
        form_fields = [TextField("name")]

    admin = DemoAdmin()
    admin.storage = storage

    row = product_model(name="/media/covers/old.png", price=1)
    session.add(row)
    await session.commit()

    await admin.update(session, row.id, {"name": "/media/covers/new.png"})
    assert storage.deleted == ["covers/old.png"]

    storage.deleted.clear()
    await admin.update(session, row.id, {"name": "/media/covers/new.png"})
    assert storage.deleted == []


def test_object_key_resolution():
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"
        media_base_url = "/media"

    admin = DemoAdmin()

    assert admin._object_key("/media/a/b.png") == "a/b.png"
    assert admin._object_key("https://cdn/x.png") is None
    assert admin._object_key("") is None
    assert admin._object_key(None) is None


async def test_relation_options_dispatch_and_missing():
    from fastkit_core.errors.exceptions import NotFoundError
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"

        async def options_category_id(self, session, parent_values, locale):
            return [{"value": 1, "label": parent_values.get("scope", "all")}]

    admin = DemoAdmin()

    options = await admin.relation_options(None, "category_id", {"scope": "active"}, "en")
    assert options == [{"value": 1, "label": "active"}]

    with pytest.raises(NotFoundError):
        await admin.relation_options(None, "missing", {}, "en")


def test_virtual_field_skipped_in_parse_and_detail():
    from fastkit_admin.fields import AdminField, TextField
    from fastkit_admin.resource import AdminResource

    class Row:
        id = "1"
        name = "Ada"

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), AdminField("extra", virtual=True)]

    admin = DemoAdmin()

    parsed = admin._parse_and_validate({"name": "Ada", "extra": "ignored"}, "en", partial=False)
    assert parsed == {"name": "Ada"}

    detail = admin.serialize_detail(Row(), "en")
    assert detail == {"id": "1", "_display": "1", "name": "Ada", "_html": {}}


def test_display_uses_model_display_label():
    from fastkit_admin.resource import AdminResource

    class Row:
        id = 7

        def display_label(self):
            return "Starter Plan"

    class DemoAdmin(AdminResource):
        name = "demo"

    admin = DemoAdmin()

    assert admin.display(Row()) == "Starter Plan"
    assert admin.serialize_detail(Row(), "en")["_display"] == "Starter Plan"


def test_column_explicit_type_and_html_flag():
    from fastkit_admin.columns import Column
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"
        list_columns = [Column("created_at", type="datetime"), Column("badge")]

        def render_badge(self, row, locale):
            return "<b>x</b>"

    admin = DemoAdmin()
    schemas = {item["name"]: item for item in admin.grid_schema()["columns"]}

    assert schemas["created_at"]["field_type"] == "datetime"
    assert schemas["created_at"]["html"] is False
    assert schemas["badge"]["html"] is True


def test_filters_split_into_widgets_and_fieldsets():
    from fastkit_admin.filters import TextFilter
    from fastkit_admin.resource import AdminResource, Fieldset

    class DemoAdmin(AdminResource):
        name = "demo"
        filters = [Fieldset("Target", ["name"]), TextFilter("name")]

    schema = DemoAdmin().grid_schema()

    assert [item["field"] for item in schema["filters"]] == ["name"]
    assert schema["filter_fieldsets"] == [{"title": "Target", "description": None, "fields": ["name"]}]


def test_grid_value_serializes_temporal_and_decimal():
    from datetime import date, datetime, time
    from decimal import Decimal

    from fastkit_admin.resource import _grid_value

    assert _grid_value(date(2026, 7, 15)) == "2026-07-15"
    assert _grid_value(datetime(2026, 7, 15, 9, 30)) == "2026-07-15T09:30:00+00:00"
    assert _grid_value(time(9, 30)) == "09:30:00"

    from datetime import timezone as _tz
    aware = datetime(2026, 7, 15, 9, 30, tzinfo=_tz.utc)
    assert _grid_value(aware) == "2026-07-15T09:30:00+00:00"
    assert _grid_value(Decimal("19.90")) == "19.90"
    assert _grid_value("plain") == "plain"


def test_number_field_format_passthrough():
    from fastkit_admin.fields import NumberField

    assert NumberField("age").format_value(42) == 42


def test_plain_helper():
    from datetime import date

    from fastkit_admin.resource import _plain

    assert _plain(None) is None
    assert _plain("x") == "x"
    assert _plain(5) == 5
    assert _plain(date(2026, 7, 14)) == "2026-07-14"


async def test_permission_flags(product_admin):
    async def allow_all(permission):
        return True

    async def only_view(permission):
        return permission == "products.view"

    assert (await product_admin.permission_flags(allow_all))["can_delete"] is True
    flags = await product_admin.permission_flags(only_view)
    assert flags["can_list"] is True
    assert flags["can_create"] is False


async def test_run_action_and_missing(session, product_admin, product_model):
    from fastkit_core.errors.exceptions import NotFoundError

    row = await product_admin.create(session, {"name": "Act", "price": "5.00", "is_active": "true"}, "en")

    result = await product_admin.run_action(session, "deactivate", [row.id], "en")
    assert result == {"deactivated": 1}

    # an action returning None falls back to a default affected count
    touched = await product_admin.run_action(session, "touch", [row.id], "en")
    assert touched == {"affected": 1}

    with pytest.raises(NotFoundError):
        product_admin.get_action("ghost")


async def test_create_and_update_map_unique_violation_to_conflict(session, tag_model):
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource
    from fastkit_core.errors.exceptions import ConflictError

    class TagAdmin(AdminResource):
        name = "tags"
        model = tag_model
        list_columns = ["slug"]
        form_fields = [TextField("slug")]

    admin = TagAdmin()
    await admin.create(session, {"slug": "news"}, "en")
    other_id = (await admin.create(session, {"slug": "sports"}, "en")).id

    with pytest.raises(ConflictError):
        await admin.create(session, {"slug": "news"}, "en")

    with pytest.raises(ConflictError):
        await admin.update(session, other_id, {"slug": "news"}, "en")


async def test_run_action_declared_without_a_handler_raises(session, product_model):
    from fastkit_admin.actions import AdminAction
    from fastkit_admin.fields import TextField
    from fastkit_admin.resource import AdminResource
    from fastkit_core.errors.exceptions import NotFoundError

    class Orphaned(AdminResource):
        name = "products"
        model = product_model
        list_columns = ["name"]
        form_fields = [TextField("name")]
        actions = [AdminAction(name="orphan", label="Orphan", scope="bulk")]

    with pytest.raises(NotFoundError):
        await Orphaned().run_action(session, "orphan", [], "en")


def test_grid_schema_defaults(product_admin):
    grid = product_admin.grid_schema()

    assert grid["flags"] == {}
    assert any(action["name"] == "deactivate" for action in grid["actions"])
    align = {column["name"]: column["align"] for column in grid["columns"]}
    assert align["price"] == "right"


async def test_password_field_skipped_when_blank():
    from fastkit_admin.fields import PasswordField, TextField
    from fastkit_admin.resource import AdminResource

    class DemoAdmin(AdminResource):
        name = "demo"
        form_fields = [TextField("name"), PasswordField("password")]

    admin = DemoAdmin()
    parsed = admin._parse_and_validate({"name": "Ada", "password": ""}, "en", partial=True)

    assert "password" not in parsed
    assert parsed["name"] == "Ada"


