import re
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from enums.purchase_status import PurchaseStatus
from enums.subscription_status import SubscriptionStatus
from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.dates import as_utc, now
from helpers.security import create_token
from models.user import User
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from reports.purchases_report import PurchasesReport
from services.user_service import user_service
from tests.factories import make_integration, make_plan, make_product, make_purchase, make_subscription, make_tenant, save


def headers_of(user) -> dict:
    return {"Authorization": f"Bearer {create_token(user.token, user.role, user.session_epoch)}"}


async def an_editor(db, tenant=None):
    return await user_service.create(db, {"username": "writer", "email": "writer@acme.com", "password": "s3cret-password", "role": UserRole.EDITOR, "status": UserStatus.ACTIVE, "tenant_id": tenant.id if tenant else None})


async def set_timezone(db, username: str, zone: str) -> None:
    account = await db.scalar(select(User).where(User.username == username))
    account.timezone = zone
    await db.commit()


def period(days: int = 1) -> dict:
    today = now().date()

    return {"startsOn": (today - timedelta(days=days)).isoformat(), "endsOn": today.isoformat()}


async def test_a_report_says_its_title_its_formats_and_the_filter_it_opens_with(client, admin_headers):
    answer = (await client.get("/api/reports/purchases", headers=admin_headers)).json()
    today = now().date()

    assert answer["title"] == "Purchases"
    assert [format["code"] for format in answer["formats"]] == ["pdf", "excel"]
    assert answer["formats"][0]["label"] == "PDF"
    assert answer["defaultFilter"] == {"startsOn": (today - timedelta(days=30)).isoformat(), "endsOn": today.isoformat()}


async def test_a_report_with_no_filter_of_its_own_waits_for_one(client, admin_headers):
    answer = (await client.get("/api/reports/subscriptions", headers=admin_headers)).json()

    assert answer["defaultFilter"] is None
    assert [format["code"] for format in answer["formats"]] == ["pdf", "excel", "csv"]


async def test_the_rows_are_written_the_way_the_operator_reads_them(client, db, tenant, member, admin_headers):
    product = await make_product(db, tenant, name="Handbook", price=Decimal("1234.5"))
    purchase = await make_purchase(db, tenant, member, product, status=PurchaseStatus.PAID, reference="purchase-one")
    await set_timezone(db, "root", "America/Sao_Paulo")

    answer = (await client.get("/api/reports/purchases/rows", params=period(), headers=admin_headers | {"Accept-Language": "pt"})).json()
    opened = as_utc(purchase.created_at).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M")

    assert answer["count"] == 1
    assert [column["key"] for column in answer["columns"]] == ["reference", "createdAt", "email", "product", "status", "price", "paidAt"]
    assert answer["columns"][1]["label"] == "Aberta em"
    assert answer["rows"][0] == {"reference": "purchase-one", "createdAt": opened, "email": "reader@acme.com", "product": "Handbook", "status": "Paga", "price": "USD 1.234,50", "paidAt": None}


async def test_a_period_is_read_from_the_first_minute_of_its_first_day_to_the_last_of_its_last_on_the_clock_of_the_operator(client, db, tenant, member, admin_headers):
    product = await make_product(db, tenant)
    zone = ZoneInfo("America/Sao_Paulo")
    await set_timezone(db, "root", "America/Sao_Paulo")

    for reference, local in (("purchase-before", datetime(2026, 3, 1, 23, 59)), ("purchase-first", datetime(2026, 3, 2, 0, 0)), ("purchase-last", datetime(2026, 3, 3, 23, 59)), ("purchase-after", datetime(2026, 3, 4, 0, 0))):
        await make_purchase(db, tenant, member, product, reference=reference, created_at=local.replace(tzinfo=zone))

    answer = (await client.get("/api/reports/purchases/rows", params={"startsOn": "2026-03-02", "endsOn": "2026-03-03"}, headers=admin_headers)).json()

    assert [row["reference"] for row in answer["rows"]] == ["purchase-last", "purchase-first"]


async def test_the_filter_narrows_the_rows(client, db, tenant, member, admin_headers):
    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product, status=PurchaseStatus.PAID)
    await make_purchase(db, tenant, member, product, status=PurchaseStatus.FAILED)

    answer = (await client.get("/api/reports/purchases/rows", params=period() | {"status": "failed"}, headers=admin_headers)).json()

    assert answer["count"] == 1
    assert answer["rows"][0]["status"] == "Failed"


async def test_a_filter_the_report_cannot_read_is_refused_on_the_field_it_names(client, admin_headers):
    reversed_period = await client.get("/api/reports/purchases/rows", params={"startsOn": "2026-02-02", "endsOn": "2026-01-01"}, headers=admin_headers)
    missing = await client.get("/api/reports/purchases/rows", params={"startsOn": "2026-02-02"}, headers=admin_headers)
    unknown = await client.get("/api/reports/purchases/rows", params=period() | {"tenant": "1"}, headers=admin_headers)
    unreadable = await client.get("/api/reports/purchases/rows", params=period() | {"status": "lost"}, headers=admin_headers)

    assert reversed_period.status_code == 422
    assert "endsOn" in reversed_period.json()["errors"]
    assert "endsOn" in missing.json()["errors"]
    assert unknown.status_code == 422
    assert "tenant" in unknown.json()["errors"]
    assert "status" in unreadable.json()["errors"]


async def test_a_day_past_what_the_calendar_holds_on_every_clock_is_refused_and_never_breaks_the_query(client, admin_headers):
    answer = await client.get("/api/reports/purchases/rows", params={"startsOn": "9999-12-30", "endsOn": "9999-12-31"}, headers=admin_headers)

    assert answer.status_code == 422
    assert "endsOn" in answer.json()["errors"]


async def test_a_filter_that_selects_more_than_a_report_carries_is_sent_back_to_be_narrowed(client, db, tenant, member, admin_headers, monkeypatch):
    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product)
    await make_purchase(db, tenant, member, product)

    monkeypatch.setattr(PurchasesReport, "row_limit", 1)

    answer = await client.get("/api/reports/purchases/rows", params=period(), headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.report-too-large"
    assert "1" in answer.json()["detail"]


@pytest.mark.parametrize(("format", "media_type", "opening"), [("pdf", "application/pdf", b"%PDF-"), ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK")])
async def test_a_report_is_taken_away_in_each_format_it_offers(client, db, tenant, member, admin_headers, format, media_type, opening):
    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product)

    answer = await client.get(f"/api/reports/purchases/export/{format}", params=period(), headers=admin_headers)

    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith(media_type)
    assert answer.headers["content-disposition"].startswith('attachment; filename="purchases-')
    assert answer.content.startswith(opening)
    assert answer.headers["cache-control"] == "private, no-store"


async def test_a_spreadsheet_keeps_an_amount_a_number(client, db, tenant, member, admin_headers):
    product = await make_product(db, tenant, price=Decimal("19.9"))
    await make_purchase(db, tenant, member, product)

    answer = await client.get("/api/reports/purchases/export/excel", params=period(), headers=admin_headers)
    book = zipfile.ZipFile(BytesIO(answer.content))
    names = re.findall(r'<sheet name="([^"]+)"', book.read("xl/workbook.xml").decode())
    sheet = book.read("xl/worksheets/sheet2.xml").decode()

    assert names == ["Charts", "Purchases"]
    assert "<v>19.9</v>" in sheet
    assert "&quot;USD&quot; #,##0.00" in book.read("xl/styles.xml").decode()


async def test_a_custom_format_is_offered_only_by_the_report_that_lists_it(client, db, tenant, member, admin_headers):
    plan = await make_plan(db, tenant, name="Monthly")
    integration = await make_integration(db, tenant)
    await make_subscription(db, tenant, member, plan, integration_id=integration.id, status=SubscriptionStatus.ACTIVE, started_at=None)

    csv = await client.get("/api/reports/subscriptions/export/csv", params={"status": "active", "provider": "stripe"}, headers=admin_headers)
    started = await client.get("/api/reports/subscriptions/rows", params={"startedFrom": now().date().isoformat()}, headers=admin_headers)
    elsewhere = await client.get("/api/reports/purchases/export/csv", params=period(), headers=admin_headers)

    assert csv.status_code == 200
    assert csv.content.decode("utf-8-sig").splitlines() == ["Email,Plan,Status,Provider,Started at,Access until", "reader@acme.com,Monthly,Active,Stripe,,"]
    assert started.json()["count"] == 0
    assert elsewhere.status_code == 404


async def test_a_report_nobody_wrote_is_one_that_does_not_exist(client, admin_headers):
    assert (await client.get("/api/reports/revenue", headers=admin_headers)).status_code == 404


async def test_a_reader_outside_the_panel_reaches_no_report(client, member_headers):
    assert (await client.get("/api/reports/purchases", headers=member_headers)).status_code == 403


async def test_a_report_reached_through_a_group_is_read_by_its_members_and_nobody_else(client, db):
    editor = await an_editor(db)

    assert (await client.get("/api/reports/subscriptions", headers=headers_of(editor))).status_code == 404

    group = await save(db, UserGroup(code="finance", name="Finance"))
    await save(db, UserGroupMember(group_id=group.id, user_id=editor.id))

    assert (await client.get("/api/reports/subscriptions", headers=headers_of(editor))).status_code == 200
    assert (await client.get("/api/reports/purchases", headers=headers_of(editor))).status_code == 404


async def test_the_menu_names_the_reports_the_account_reaches(client, db, admin_headers, member_headers):
    editor = await an_editor(db)
    group = await save(db, UserGroup(code="finance", name="Finance"))
    await save(db, UserGroupMember(group_id=group.id, user_id=editor.id))

    assert (await client.get("/api/meta/permissions", headers=admin_headers)).json()["reports"] == ["purchases", "subscriptions"]
    assert (await client.get("/api/meta/permissions", headers=headers_of(editor))).json()["reports"] == ["subscriptions"]
    assert (await client.get("/api/meta/permissions", headers=member_headers)).json()["reports"] == []


async def test_an_operator_of_a_brand_reads_the_rows_of_that_brand_alone(client, db, tenant, member):
    operator = await user_service.create(db, {"username": "brandadmin", "email": "brandadmin@acme.com", "password": "s3cret-password", "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
    other = await make_tenant(db, code="other", domain="other.test")
    stranger = await user_service.create(db, {"username": "stranger", "email": "stranger@acme.com", "password": "s3cret-password", "status": UserStatus.ACTIVE, "tenant_id": other.id})
    await make_purchase(db, tenant, member, await make_product(db, tenant), reference="purchase-ours")
    await make_purchase(db, other, stranger, await make_product(db, other), reference="purchase-theirs")

    answer = (await client.get("/api/reports/purchases/rows", params=period(), headers=headers_of(operator))).json()

    assert [row["reference"] for row in answer["rows"]] == ["purchase-ours"]


async def test_the_subscriptions_are_narrowed_to_the_days_they_started_in(client, db, tenant, member, admin_headers):
    plan = await make_plan(db, tenant, name="Monthly")
    today = now().date()
    await make_subscription(db, tenant, member, plan, started_at=now() - timedelta(days=40))
    await make_subscription(db, tenant, member, plan, started_at=now())

    recent = await client.get("/api/reports/subscriptions/rows", params={"startedFrom": (today - timedelta(days=1)).isoformat(), "startedUntil": today.isoformat()}, headers=admin_headers)
    reversed_period = await client.get("/api/reports/subscriptions/rows", params={"startedFrom": today.isoformat(), "startedUntil": (today - timedelta(days=1)).isoformat()}, headers=admin_headers)

    assert recent.json()["count"] == 1
    assert reversed_period.status_code == 422
    assert "startedUntil" in reversed_period.json()["errors"]
