from fastkit_admin.rendering import AdminRenderer
from fastkit_admin.screens import detail_context, form_context, list_context, profile_context, report_context


def _schema():
    return {
        "resource": "products",
        "label": "Products",
        "columns": [
            {"name": "name", "label": "Name", "align": None, "sortable": True, "clickable": False, "field_type": "text", "html": False},
            {"name": "is_active", "label": "Active", "align": None, "sortable": False, "clickable": False, "field_type": "boolean", "html": False},
        ],
        "filters": [],
        "filter_fieldsets": [],
        "actions": [],
        "search_fields": ["name"],
        "default_sort": ["-id"],
        "page_size": 25,
        "page_size_options": [10, 25],
        "select_all": False,
        "permissions": {},
        "flags": {"can_list": True, "can_detail": True, "can_create": True, "can_update": True, "can_delete": True},
    }


def _result():
    return {
        "rows": [{"id": "1", "name": "Widget", "is_active": True}, {"id": "2", "name": "Gadget", "is_active": False}],
        "pagination": {"strategy": "offset", "page": 1, "page_size": 25, "total_items": 2, "total_pages": 1, "has_previous": False, "has_next": False},
    }


def _render(context):
    return AdminRenderer().render("admin/partials/_table.html", t=lambda key, **params: key, **context)


def test_list_context_shapes_columns_sort_and_paging():
    context = list_context(_schema(), _result(), "/admin", None, None)

    assert context["base_url"] == "/admin/products"
    assert context["has_bulk"] is True
    assert context["columns"][0]["sort_value"] == "name"
    assert context["columns"][0]["sort_active"] is False
    assert context["showing_from"] == 1
    assert context["showing_to"] == 2
    assert context["showing_total"] == 2


def test_list_context_marks_the_active_sort_column_descending():
    context = list_context(_schema(), _result(), "/admin", None, "name")

    name_column = context["columns"][0]
    assert name_column["sort_active"] is True
    assert name_column["sort_desc"] is False
    assert name_column["sort_value"] == "-name"


def test_table_partial_renders_rows_cells_and_actions():
    html = _render(list_context(_schema(), _result(), "/admin", None, None))

    assert 'data-testid="row-1"' in html
    assert "Widget" in html
    assert "ti-check text-green" in html
    assert "ti-x text-red" in html
    assert 'href="/admin/products/1/edit"' in html
    assert 'data-testid="view-1"' in html
    assert 'data-testid="delete-2"' in html


def _schema_with_filters():
    schema = _schema()
    schema["filters"] = [
        {"field": "name", "type": "text", "label": "Name"},
        {"field": "is_active", "type": "boolean", "label": "Active"},
        {"field": "created_at", "type": "date_range", "label": "Created"},
        {"field": "category", "type": "choice", "label": "Category", "choices": [{"value": "a", "label": "A"}]},
    ]
    schema["filter_fieldsets"] = [{"title": "Dates", "description": None, "fields": ["created_at"]}]

    return schema


def test_list_context_attaches_filter_values_and_groups():
    context = list_context(_schema_with_filters(), _result(), "/admin", None, None, applied_filters={"name": "wid", "created_at": {"from": "2026-01-01", "to": "2026-02-01"}})

    assert context["has_filters"] is True
    name_filter = next(item for item in context["filters"] if item["field"] == "name")
    assert name_filter["value"] == "wid"
    range_filter = next(item for item in context["filters"] if item["field"] == "created_at")
    assert range_filter["value_from"] == "2026-01-01"
    assert range_filter["value_to"] == "2026-02-01"

    titles = [group["title"] for group in context["filter_groups"]]
    assert "Dates" in titles
    assert None in titles


def test_filter_panel_renders_widgets_by_type():
    context = list_context(_schema_with_filters(), _result(), "/admin", None, None, applied_filters={"name": "wid"})
    html = AdminRenderer().render("admin/partials/_filter_panel.html", t=lambda key, **params: key, **context)

    assert 'name="filter[name]"' in html
    assert 'value="wid"' in html
    assert 'name="filter[is_active]"' in html
    assert 'name="filter[created_at][from]"' in html
    assert 'data-testid="filter-apply"' in html
    assert 'data-testid="filter-clear"' in html


def _report():
    return {
        "title": "Sales",
        "columns": [{"key": "category", "label": "Category", "align": "left"}, {"key": "total", "label": "Total", "align": "right"}],
        "rows": [{"category": "A", "total": 100}, {"category": "B", "total": None}],
        "formats": ["csv", "pdf"],
        "filters": [{"field": "category", "type": "choice", "label": "Category", "choices": [{"value": "a", "label": "A"}]}],
    }


def test_report_context_and_table_render():
    context = report_context(_report(), "sales", "/admin", "/api")

    assert context["base_url"] == "/admin/reports/sales"
    assert context["has_filters"] is True

    html = AdminRenderer().render("admin/partials/_report_table.html", t=lambda key, **params: key, **context)

    assert "Category" in html
    assert 'data-testid="report-row"' in html
    assert "100" in html
    assert "—" in html
    assert 'href="/api/reports/sales/export.csv"' in html
    assert 'data-testid="report-export-pdf"' in html


def test_profile_context_and_partial_render():
    profile = {"email": "root@x.com", "display_name": "Root", "first_name": "", "last_name": "", "avatar_url": None, "identifiers": [{"id": "1", "type": "email", "value": "root@x.com"}], "identifier_types": ["email", "phone"]}
    context = profile_context(profile, "/admin", "/api")

    assert context["initials"] == "RO"
    assert context["email"] == "root@x.com"

    html = AdminRenderer().render("admin/partials/_profile.html", t=lambda key, **params: key, **context)

    assert 'data-testid="profile-avatar"' in html
    assert "RO" in html
    assert 'data-testid="profile-save"' in html
    assert 'data-testid="profile-password-save"' in html
    assert 'data-testid="identifier-delete-email"' in html
    assert 'data-testid="identifier-add"' in html
    assert '<option value="phone">' in html


def _field(**overrides):
    base = {"name": "title", "type": "text", "label": "Title", "value": None, "required": False, "readonly": False, "help_text": None, "placeholder": None, "hide_label": False}
    base.update(overrides)

    return base


def _render_field(field):
    return AdminRenderer().render("admin/partials/_field.html", t=lambda key, **params: key, field=field)


def test_form_context_attaches_values_and_drops_empty_fieldsets():
    schema = {
        "fieldsets": [
            {"title": "Identity", "description": None, "fields": [_field(name="name", label="Name")]},
            {"title": "Empty", "description": None, "fields": []},
        ]
    }

    context = form_context(schema, {"name": "Widget"}, "Products", "edit", "/admin", "products", record_id="1")

    assert len(context["fieldsets"]) == 1
    assert context["fieldsets"][0]["fields"][0]["value"] == "Widget"
    assert context["record_id"] == "1"
    assert context["base_url"] == "/admin/products"


def test_field_partial_renders_text_input_with_value_and_error_slot():
    html = _render_field(_field(value="Hi", required=True))

    assert 'type="text"' in html
    assert 'value="Hi"' in html
    assert 'data-error="title"' in html


def test_field_partial_renders_password_and_boolean_and_select():
    password = _render_field(_field(name="pw", type="password"))
    assert 'type="password"' in password
    assert 'autocomplete="new-password"' in password

    boolean = _render_field(_field(name="active", type="boolean", value=True))
    assert 'type="checkbox"' in boolean
    assert "checked" in boolean

    select = _render_field(_field(name="cat", type="select", value="a", choices=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]))
    assert 'value="a" selected' in select


def test_complex_field_partials_render_mount_containers():
    richtext = _render_field(_field(name="body", type="richtext", upload_url="/api/uploads/image", value="<p>Hi</p>"))
    assert 'class="fk-richtext"' in richtext
    assert 'data-upload-url="/api/uploads/image"' in richtext

    lookup = _render_field(_field(name="cat", type="lookup", depends_on=[], min_chars=0, initial_limit=10, search_limit=20, value="5"))
    assert 'class="fk-lookup"' in lookup
    assert 'data-search-limit="20"' in lookup
    assert 'value="5"' in lookup

    json_field = _render_field(_field(name="meta", type="json", value={"a": 1}))
    assert 'class="fk-json"' in json_field
    assert "data-value=" in json_field

    matrix = AdminRenderer().render(
        "admin/partials/_field.html",
        t=lambda key, **params: key,
        record_id="7",
        field=_field(name="perms", type="permission_matrix", groups_url="/meta/permissions", value_url="/roles/{id}/permissions", save_url="/roles/{id}/permissions", virtual=True),
    )
    assert 'class="fk-matrix"' in matrix
    assert 'data-groups-url="/meta/permissions"' in matrix
    assert 'data-record-id="7"' in matrix


def test_form_context_builds_inline_rows_from_data():
    price = _field(name="price", type="number", label="Price")
    schema = {"fieldsets": [], "inlines": [{"name": "items", "label": "Items", "fields": [price], "min_items": 0, "max_items": None}]}

    context = form_context(schema, None, "Order", "edit", "/admin", "orders", record_id="1", inline_data={"items": [{"price": "10"}, {"price": "20"}]})

    assert len(context["inlines"]) == 1
    inline = context["inlines"][0]
    assert len(inline["rows"]) == 2
    assert inline["rows"][0][0]["value"] == "10"
    assert inline["rows"][1][0]["value"] == "20"


def test_inline_partial_renders_rows_prototype_and_controls():
    inline = {
        "name": "items",
        "label": "Items",
        "fields": [_field(name="price", type="number", label="Price")],
        "min_items": 0,
        "max_items": 3,
        "rows": [[_field(name="price", type="number", label="Price", value="10")]],
    }

    html = AdminRenderer().render("admin/partials/inline.html", t=lambda key, **params: key, inline=inline)

    assert 'data-testid="inline-items"' in html
    assert 'data-testid="inline-add-items"' in html
    assert 'data-max="3"' in html
    assert 'value="10"' in html
    assert "fk-inline-prototype" in html
    assert "fk-inline-remove" in html


def _render_detail_field(field, record_id=None):
    return AdminRenderer().render("admin/partials/_detail_field.html", t=lambda key, **params: key, field=field, record_id=record_id)


def test_detail_context_attaches_values_and_render_html():
    schema = {"fieldsets": [{"title": "Info", "description": None, "fields": [_field(name="name", type="text", label="Name"), _field(name="status", type="text", label="Status")]}]}
    data = {"id": "1", "_display": "Widget", "name": "Widget", "status": "active", "_html": {"status": "<span class='badge'>active</span>"}}

    context = detail_context(schema, data, "Products", "/admin", "products", "1", {"can_update": True})

    assert context["display"] == "Widget"
    fields = context["fieldsets"][0]["fields"]
    assert fields[0]["value"] == "Widget"
    assert fields[0]["html"] is None
    assert fields[1]["html"] == "<span class='badge'>active</span>"


def test_detail_field_renders_value_boolean_dash_html_and_matrix():
    assert "Widget" in _render_detail_field(_field(name="name", type="text", label="Name", value="Widget", html=None))
    assert "ti-check text-green" in _render_detail_field(_field(name="active", type="boolean", label="Active", value=True, html=None))
    assert "—" in _render_detail_field(_field(name="note", type="text", label="Note", value=None, html=None))
    assert "<b>Active</b>" in _render_detail_field(_field(name="status", type="text", label="Status", value="x", html="<b>Active</b>"))

    matrix = _render_detail_field(_field(name="perms", type="permission_matrix", label="Perms", value=None, html=None, groups_url="/meta/permissions", value_url="/roles/{id}/permissions"), record_id="3")
    assert 'class="fk-matrix"' in matrix
    assert 'data-readonly="1"' in matrix
    assert 'data-record-id="3"' in matrix
