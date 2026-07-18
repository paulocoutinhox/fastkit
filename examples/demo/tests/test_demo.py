import io

from PIL import Image


def _png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (79, 70, 229)).save(buffer, format="PNG")

    return buffer.getvalue()


def _form_fields(schema):
    return [
        field
        for fieldset in schema["form"]["fieldsets"]
        for field in fieldset["fields"]
    ]


async def test_home_page_renders(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert 'data-testid="home-title"' in response.text


async def test_admin_login_page_renders(client):
    response = await client.get("/admin/login")

    assert response.status_code == 200
    assert 'data-testid="login-form"' in response.text


async def test_admin_shell_requires_authentication(client, login):
    anonymous = await client.get("/admin", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/admin/login"

    await login(client)
    authenticated = await client.get("/admin", follow_redirects=False)
    assert authenticated.status_code == 200
    assert 'data-testid="sidebar"' in authenticated.text


async def test_login_and_session(client, login):
    response = await login(client)

    assert response.status_code == 200
    assert response.json()["data"]["is_root"] is True

    session = await client.get("/api/auth/session")
    assert session.json()["data"]["email"] == "root@fastkit.local"


async def test_login_wrong_password(client, login):
    response = await login(client, password="incorrect-password")

    assert response.status_code == 401
    assert response.json()["message"]["code"] == "authentication.invalid_credentials"


async def test_logout(client, login):
    await login(client)
    await client.post("/api/auth/logout")

    assert (await client.get("/api/auth/session")).status_code == 401


async def test_navigation_is_grouped(client, login):
    await login(client)

    groups = (await client.get("/api/navigation")).json()["data"]
    keys = {group["key"] for group in groups}

    assert {"catalog", "content", "operations", "system", "internal"} <= keys
    system = next(group for group in groups if group["key"] == "system")
    assert {"tenants", "users", "roles"} <= {
        item["resource"] for item in system["items"]
    }
    operations = next(group for group in groups if group["key"] == "operations")
    assert {"scheduled-tasks", "task-runs", "report-runs"} <= {
        item["resource"] for item in operations["items"]
    }
    reports = next(group for group in groups if group["key"] == "reports")
    report_paths = {item["path"] for item in reports["items"]}
    assert any(path.endswith("/reports/sales-by-category") for path in report_paths)
    assert any(path.endswith("/reports/product-prices") for path in report_paths)
    internal = next(group for group in groups if group["key"] == "internal")
    assert {item["resource"] for item in internal["items"]} == {"activity"}


async def test_staff_navigation_excludes_access_control(client, login):
    await login(client, email="staff@fastkit.local", password="staff-password-123")

    groups = (await client.get("/api/navigation")).json()["data"]
    resources = {item["resource"] for group in groups for item in group["items"]}

    # the default staff role manages every module...
    assert {"products", "showcase", "content", "users"} <= resources
    # ...except access control, which is administrative only
    assert "roles" not in resources


async def test_permission_flags_for_staff(client, login):
    await login(client, email="staff@fastkit.local", password="staff-password-123")

    catalog = (await client.get("/api/resources/showcase/schema")).json()["data"][
        "grid"
    ]["flags"]

    assert catalog["can_create"] is True
    assert catalog["can_delete"] is True

    roles = (await client.get("/api/resources/roles/schema")).json()["data"]["grid"][
        "flags"
    ]

    assert roles["can_list"] is False
    assert roles["can_delete"] is False


async def test_product_crud_and_locale_decimal(client, login):
    await login(client)

    grid = await client.get("/api/resources/products?sort=name")
    assert grid.json()["meta"]["pagination"]["total_items"] == 3

    categories = (
        await client.get("/api/resources/products/options/category_id")
    ).json()["data"]
    category_id = categories[0]["value"]

    created = await client.post(
        "/api/resources/products",
        json={
            "name": "Add-on",
            "sku": "SKU-100",
            "price": "1.234,50",
            "category_id": category_id,
            "is_active": "true",
        },
        headers={"Accept-Language": "pt"},
    )
    assert created.status_code == 201
    identifier = created.json()["data"]["id"]

    detail = await client.get(
        f"/api/resources/products/{identifier}", headers={"Accept-Language": "pt"}
    )
    assert detail.json()["data"]["price"] == "1.234,50"
    assert detail.json()["data"]["category_id"] == category_id

    deleted = await client.delete(f"/api/resources/products/{identifier}")
    assert deleted.json()["message"]["code"] == "products.deleted"


async def test_product_grid_shows_joined_related_names(client, login):
    await login(client)

    schema = (await client.get("/api/resources/products/schema")).json()["data"]["grid"]
    assert schema["default_sort"] == ["-id"]

    grid = (await client.get("/api/resources/products?sort=id")).json()["data"]
    first = grid[0]
    assert first["category"] in {"General", "Premium"}
    assert first["subcategory"] in {"Basic", "Standard", "Pro", "Enterprise"}


async def test_relation_and_dependent_options(client, login):
    await login(client)

    categories = (
        await client.get("/api/resources/products/options/category_id")
    ).json()["data"]
    assert {entry["label"] for entry in categories} == {"General", "Premium"}
    category_id = next(
        entry["value"] for entry in categories if entry["label"] == "Premium"
    )

    # subcategory options are empty until a parent category is chosen
    without_parent = (
        await client.get("/api/resources/products/options/subcategory_id")
    ).json()["data"]
    assert without_parent == []

    dependent = (
        await client.get(
            f"/api/resources/products/options/subcategory_id?category_id={category_id}"
        )
    ).json()["data"]
    assert {entry["label"] for entry in dependent} == {"Pro", "Enterprise"}


async def test_validation_error_has_translated_message_text(client, login):
    await login(client)

    response = await client.post(
        "/api/resources/products",
        json={"sku": "NO-NAME"},
        headers={"Accept-Language": "pt"},
    )
    body = response.json()

    assert response.status_code == 422
    assert body["message"]["code"] == "validation.failed"
    assert body["message"]["text"] == "Os dados enviados são inválidos."
    name_error = [error for error in body["errors"] if error["field"] == "name"][0]
    assert name_error["code"] == "validation.required"
    assert name_error["message"] == "Este campo é obrigatório."


async def test_fastapi_body_validation_is_translated(client):
    response = await client.post(
        "/api/auth/login",
        json={"identifier": "x@y.com"},
        headers={"Accept-Language": "pt"},
    )
    body = response.json()

    assert response.status_code == 422
    password_error = [
        error for error in body["errors"] if error["field"] == "password"
    ][0]
    assert password_error["code"] == "validation.required"
    assert password_error["message"] == "Este campo é obrigatório."


async def test_grid_row_endpoint_returns_serialized_row(client, login):
    await login(client)

    grid = (await client.get("/api/resources/products")).json()["data"]
    row_id = grid[0]["id"]

    row = (await client.get(f"/api/resources/products/{row_id}/row")).json()["data"]

    assert row["id"] == row_id
    assert "name" in row


async def test_grid_schema_exposes_select_all_and_clickable(client, login):
    await login(client)

    grid = (await client.get("/api/resources/products/schema")).json()["data"]["grid"]
    name_column = next(column for column in grid["columns"] if column["name"] == "name")

    assert grid["select_all"] is True
    assert name_column["clickable"] is True


async def test_lookup_search_and_preload(client, login):
    await login(client)

    matches = (
        await client.get("/api/resources/showcase/options/category_id?q=Prem")
    ).json()["data"]
    assert {entry["label"] for entry in matches} == {"Premium"}

    value = matches[0]["value"]
    preloaded = (
        await client.get(f"/api/resources/showcase/options/category_id?value={value}")
    ).json()["data"]
    assert preloaded[0]["value"] == value


async def test_product_form_is_grouped_into_fieldsets(client, login):
    await login(client)

    schema = (await client.get("/api/resources/products/schema")).json()["data"]
    titles = [fieldset["title"] for fieldset in schema["form"]["fieldsets"]]

    assert titles == ["Details", "Classification", "Status"]
    classification = next(
        fieldset
        for fieldset in schema["form"]["fieldsets"]
        if fieldset["title"] == "Classification"
    )
    dependent = next(
        field for field in classification["fields"] if field["name"] == "subcategory_id"
    )
    assert dependent["depends_on"] == ["category_id"]


async def test_bulk_action(client, login):
    await login(client)

    grid = (await client.get("/api/resources/products")).json()
    ids = [row["id"] for row in grid["data"]]

    response = await client.post(
        "/api/resources/products/actions/deactivate", json={"ids": ids}
    )
    assert response.json()["data"]["deactivated"] == len(ids)


async def test_showcase_all_fields(client, login):
    await login(client)

    schema = (await client.get("/api/resources/showcase/schema")).json()["data"]
    field_types = {field["type"] for field in _form_fields({"form": schema["form"]})}

    assert {
        "text",
        "textarea",
        "richtext",
        "number",
        "decimal",
        "select",
        "multiselect",
        "lookup",
        "url",
        "email",
        "masked",
        "color",
        "boolean",
        "date",
        "time",
        "datetime",
        "json",
        "image",
        "file",
    } <= field_types

    created = await client.post(
        "/api/resources/showcase",
        json={
            "title": "New showcase",
            "summary": "A summary",
            "body_html": "<p>Body <script>alert(1)</script></p>",
            "quantity": "5",
            "price": "12.50",
            "status": "draft",
            "tags": ["new", "sale"],
            "brand_color": "#123abc",
            "is_featured": "true",
            "release_date": "2026-07-14",
            "release_time": "09:30",
            "published_at": "2026-07-14T09:30",
            "attributes": '{"weight": "1kg"}',
        },
    )
    assert created.status_code == 201
    data = created.json()["data"]

    # rich text was sanitized on save
    assert "script" not in data["body_html"]
    assert data["tags"] == ["new", "sale"]
    assert '"weight": "1kg"' in data["attributes"]


async def test_showcase_publish_action(client, login):
    await login(client)

    grid = (await client.get("/api/resources/showcase")).json()
    ids = [row["id"] for row in grid["data"]]

    response = await client.post(
        "/api/resources/showcase/actions/publish", json={"ids": ids}
    )
    assert response.json()["data"]["published"] == len(ids)


async def test_role_permission_editor(client, login):
    await login(client)

    grouped = (await client.get("/api/meta/permissions")).json()["data"]
    groups = {entry["group"] for entry in grouped}
    assert {"Users", "Products", "Showcase"} <= groups

    # the role form exposes the grouped permission matrix editor
    schema = (await client.get("/api/resources/roles/schema")).json()["data"]
    matrix = next(
        field
        for field in _form_fields({"form": schema["form"]})
        if field["type"] == "permission_matrix"
    )
    assert matrix["virtual"] is True
    assert matrix["groups_url"] == "/meta/permissions"

    roles = (await client.get("/api/resources/roles")).json()["data"]
    role_id = roles[0]["id"]

    first_permission = grouped[0]["permissions"][0]["id"]
    await client.put(
        f"/api/roles/{role_id}/permissions", json={"permission_ids": [first_permission]}
    )

    current = (await client.get(f"/api/roles/{role_id}/permissions")).json()
    assert current["data"]["permission_ids"] == [first_permission]


async def test_activity_log_records_actions_and_is_read_only(client, login):
    await login(client)

    kept = await client.post(
        "/api/resources/categories", json={"name": "Persisted", "is_active": "true"}
    )
    kept_id = kept.json()["data"]["id"]

    created = await client.post(
        "/api/resources/categories", json={"name": "Audited", "is_active": "true"}
    )
    category_id = created.json()["data"]["id"]
    await client.delete(f"/api/resources/categories/{category_id}")

    logs = (await client.get("/api/resources/activity?sort=-created_at")).json()["data"]
    actions = {(row["action"], row["resource_type"]) for row in logs}
    assert ("login", "auth") in actions
    assert ("create", "categories") in actions
    assert ("delete", "categories") in actions

    kept_row = next(
        row
        for row in logs
        if row["resource_type"] == "categories" and row["resource_id"] == "Persisted"
    )
    assert kept_row["user_id"] == "Root"
    assert not any(
        row["resource_id"] == kept_id
        for row in logs
        if row["resource_type"] == "categories"
    )

    flags = (await client.get("/api/resources/activity/schema")).json()["data"]["grid"][
        "flags"
    ]
    assert flags["can_list"] is True
    assert flags["can_create"] is False
    assert flags["can_delete"] is False

    blocked = await client.post("/api/resources/activity", json={"action": "hack"})
    assert blocked.status_code == 403


async def test_tenants_tasks_and_reports_resources(client, login):
    await login(client)

    tenants = (await client.get("/api/resources/tenants?sort=name")).json()["data"]
    assert {row["name"] for row in tenants} >= {"Acme Inc.", "Globex"}

    task_runs = (await client.get("/api/resources/task-runs")).json()["data"]
    statuses = {row["status"] for row in task_runs}
    assert "succeeded" in " ".join(statuses) or any(
        "succeeded" in status for status in statuses
    )
    assert any("badge" in row["status"] for row in task_runs)

    reports = (await client.get("/api/resources/report-runs")).json()["data"]
    assert {row["report_name"] for row in reports} >= {"sales.summary", "tenant.usage"}

    scheduled = (await client.get("/api/resources/scheduled-tasks?sort=name")).json()[
        "data"
    ]
    assert {row["name"] for row in scheduled} >= {"Hourly sync", "Nightly cleanup"}

    running = (
        await client.get("/api/resources/task-runs?filter[status]=running")
    ).json()["data"]
    assert [row["task_name"] for row in running] == ["demo.sync"]
    leased = (
        await client.get("/api/resources/task-runs?filter[status]=leased")
    ).json()["data"]
    assert leased == []

    blocked = await client.post("/api/resources/task-runs", json={"task_name": "x"})
    assert blocked.status_code == 403


async def test_viewer_is_denied_on_mutations_and_other_resources(client, login):
    await login(client, email="viewer@fastkit.local", password="viewer-password-123")

    assert (await client.get("/api/resources/products")).status_code == 200
    assert (
        await client.post(
            "/api/resources/products", json={"name": "x", "sku": "y", "price": "1"}
        )
    ).status_code == 403
    assert (await client.get("/api/resources/users/1")).status_code == 403
    assert (
        await client.post(
            "/api/resources/task-runs/actions/enqueue_email", json={"ids": []}
        )
    ).status_code == 403


async def test_reports_run_and_export(client, login):
    await login(client)

    listing = (await client.get("/api/reports")).json()["data"]
    names = {report["name"] for report in listing["reports"]}
    assert {"sales-by-category", "product-prices"} <= names
    assert {"csv", "html", "pdf"} <= set(listing["formats"])

    run = (await client.get("/api/reports/sales-by-category/run")).json()["data"]
    assert run["title"] == "Sales by category"
    assert [column["key"] for column in run["columns"]] == [
        "category",
        "products",
        "total",
    ]
    assert [f["field"] for f in run["filters"]] == ["category_id"]
    assert run["filters"][0]["type"] == "lookup"
    assert any(row["category"] == "General" for row in run["rows"])

    options = (
        await client.get("/api/reports/sales-by-category/options/category_id")
    ).json()["data"]
    premium_id = next(
        entry["value"] for entry in options if entry["label"] == "Premium"
    )

    filtered = (
        await client.get(f"/api/reports/sales-by-category/run?category_id={premium_id}")
    ).json()["data"]
    assert [row["category"] for row in filtered["rows"]] == ["Premium"]

    csv_export = await client.get(
        f"/api/reports/sales-by-category/export.csv?category_id={premium_id}"
    )
    assert csv_export.status_code == 200
    assert b"Premium" in csv_export.content and b"General" not in csv_export.content

    pdf_export = await client.get("/api/reports/product-prices/export.pdf")
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"] == "application/pdf"
    assert pdf_export.content[:4] == b"%PDF"

    denied = await client_as_viewer(client, login)
    assert (await denied.get("/api/reports")).status_code == 403


async def client_as_viewer(client, login):
    await login(client, email="viewer@fastkit.local", password="viewer-password-123")

    return client


async def test_enqueue_task_action(client, login):
    await login(client)

    response = await client.post(
        "/api/resources/task-runs/actions/enqueue_email", json={"ids": []}
    )
    assert response.status_code == 200
    assert response.json()["data"]["enqueued"]

    runs = (await client.get("/api/resources/task-runs?sort=-created_at")).json()[
        "data"
    ]
    assert any(row["task_name"] == "demo.send_welcome_email" for row in runs)


async def test_tenant_crud(client, login):
    await login(client)

    created = await client.post(
        "/api/resources/tenants",
        json={
            "name": "Initech",
            "code": "initech",
            "status": "active",
            "is_active": "true",
            "default_locale": "en",
            "timezone": "UTC",
        },
    )
    assert created.status_code == 201
    tenant_id = created.json()["data"]["id"]

    detail = (await client.get(f"/api/resources/tenants/{tenant_id}")).json()["data"]
    assert detail["_display"] == "Initech"

    await client.delete(f"/api/resources/tenants/{tenant_id}")


async def test_content_manager_per_language(client, login):
    await login(client)

    languages = (await client.get("/api/content/languages")).json()["data"]
    assert {language["code"] for language in languages} == {"en", "pt", "es"}

    created = await client.post(
        "/api/resources/content", json={"key": "home.hero", "type": "html"}
    )
    content_id = created.json()["data"]["id"]

    await client.put(
        f"/api/content/{content_id}/translations",
        json={
            "translations": [
                {"language": "en", "body": "<p>Welcome</p>"},
                {"language": "pt", "body": "<p>Bem-vindo</p>"},
                {"language": "de", "body": "<p>ignored</p>"},
            ]
        },
    )

    stored = (await client.get(f"/api/content/{content_id}/translations")).json()[
        "data"
    ]["translations"]
    by_language = {row["language"]: row["body"] for row in stored}
    assert by_language["en"] == "<p>Welcome</p>"
    assert by_language["pt"] == "<p>Bem-vindo</p>"
    assert "de" not in by_language

    english = (await client.get("/api/content-by-key/home.hero?language=en")).json()[
        "data"
    ]
    assert english["body"] == "<p>Welcome</p>"
    portuguese = (await client.get("/api/content-by-key/home.hero?language=pt")).json()[
        "data"
    ]
    assert portuguese["body"] == "<p>Bem-vindo</p>"


async def test_content_form_exposes_translations_editor(client, login):
    await login(client)

    schema = (await client.get("/api/resources/content/schema")).json()["data"]
    editor = next(
        field
        for field in _form_fields({"form": schema["form"]})
        if field["type"] == "translations"
    )

    assert editor["virtual"] is True
    assert editor["languages_url"] == "/content/languages"


async def test_non_staff_cannot_access_admin_panel(client, demo, login):
    _, runtime = demo
    account_service = runtime.component("account_service")
    password_service = runtime.component("password_service")

    await account_service.create_user(
        tenant_id=0,
        identifiers=[("email", "member@fastkit.local")],
        display_name="Member",
        is_staff=False,
        password_hash=password_service.hash("member-password-123"),
    )

    response = await login(
        client, email="member@fastkit.local", password="member-password-123"
    )

    assert response.status_code == 403
    assert response.json()["message"]["code"] == "authorization.denied"
    assert (await client.get("/api/auth/session")).status_code == 401


async def test_profile_flow(client, login):
    await login(client)

    profile = (await client.get("/api/profile")).json()["data"]
    assert profile["email"] == "root@fastkit.local"
    assert profile["identifiers"][0]["type"] == "email"

    updated = await client.put(
        "/api/profile", json={"display_name": "Root Admin", "timezone": "Europe/Lisbon"}
    )
    assert updated.json()["data"]["display_name"] == "Root Admin"

    password = await client.post(
        "/api/profile/password",
        json={
            "current_password": "root-password-123",
            "new_password": "brand-new-password-1",
        },
    )
    assert password.json()["message"]["code"] == "profile.password_changed"

    added = await client.post(
        "/api/profile/identifiers", json={"type": "phone", "value": "+5511999998888"}
    )
    assert any(item["type"] == "phone" for item in added.json()["data"]["identifiers"])


async def test_profile_avatar_and_upload(client, login):
    await login(client)

    avatar = await client.post(
        "/api/profile/avatar", files={"file": ("a.png", _png_bytes(), "image/png")}
    )
    assert avatar.json()["data"]["url"].startswith("/media/")

    image = await client.post(
        "/api/uploads/image", files={"file": ("editor.png", _png_bytes(), "image/png")}
    )
    assert image.json()["data"]["url"].startswith("/media/")

    document = await client.post(
        "/api/uploads/file", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert document.json()["data"]["url"].startswith("/media/")

    unknown = await client.post(
        "/api/uploads/other",
        files={"file": ("x.bin", b"x", "application/octet-stream")},
    )
    assert unknown.status_code == 404


async def test_gdpr_export_and_erase(client, login):
    await login(client, email="staff@fastkit.local", password="staff-password-123")

    export = await client.get("/api/gdpr/export")
    assert export.json()["data"]["email"] == "staff@fastkit.local"

    erase = await client.post("/api/gdpr/delete")
    assert erase.json()["message"]["code"] == "gdpr.erased"

    assert (await client.get("/api/auth/session")).status_code == 401


async def test_deleting_user_cascades_roles(client, login, demo):
    await login(client)
    _, runtime = demo

    from sqlalchemy import select, func

    from fastkit_permissions.models import UserRole

    users = (await client.get("/api/resources/users")).json()["data"]
    staff_id = next(
        user["id"] for user in users if user["email"] == "staff@fastkit.local"
    )

    database = runtime.component("database")

    async with database.session_factory() as session:
        before = (
            await session.execute(select(func.count()).select_from(UserRole))
        ).scalar_one()

    await client.delete(f"/api/resources/users/{staff_id}")

    async with database.session_factory() as session:
        after = (
            await session.execute(select(func.count()).select_from(UserRole))
        ).scalar_one()

    assert after < before


async def test_in_process_worker_runs_enqueued_task(monkeypatch, tmp_path):
    import asyncio

    from fastkit_db.base import Base
    from fastkit_tasks.models import TaskExecution

    from app.main import build_app

    monkeypatch.setenv("FASTKIT__TASKS__RUN_WORKER", "true")
    monkeypatch.setenv(
        "FASTKIT__DATABASE__URL", f"sqlite+aiosqlite:///{tmp_path}/worker.db"
    )
    monkeypatch.setenv("FASTKIT__CACHE__DIRECTORY", str(tmp_path / "cache"))
    monkeypatch.setenv("FASTKIT__STORAGE__ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("FASTKIT__MAIL__PROVIDER", "memory")

    application = build_app("test")
    runtime = application.state.fastkit
    await runtime.component("database").create_all(Base.metadata)
    await runtime.start()

    try:
        queue = runtime.component("task_queue")
        execution = await queue.enqueue(
            "demo.send_welcome_email", payload={"template": "welcome"}, queue="emails"
        )
        session_factory = runtime.component("database").session_factory
        status = None

        for _ in range(100):
            await asyncio.sleep(0.05)

            async with session_factory() as session:
                status = (await session.get(TaskExecution, execution.id)).status

            if status == "succeeded":
                break

        assert status == "succeeded"
    finally:
        await runtime.stop()
