from sqlalchemy import func, select

from enums.commerce import PurchaseStatus
from enums.subscription import BenefitType
from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from models.account import CreditTransaction
from models.banner import Banner
from models.commerce import Product, Purchase, UserProduct
from models.content import Content
from models.event import AppEvent
from models.gallery import Gallery, GalleryPhoto
from models.integration import ExternalProduct, Integration, WebhookEvent
from models.subscription import Benefit, BenefitGrant, Entitlement, Plan, PlanEntitlement, Subscription, SubscriptionBenefit, UserEntitlement
from models.system_log import SystemLog
from models.user import User, UserAddress
from services.commerce import commerce_service
from services.delivery import delivery_service
from services.system_log import system_log_service
from tests.factories import make_address, make_banner, make_benefit, make_content, make_entitlement, make_external_product, make_gallery, make_gallery_photo, make_integration, make_plan, make_plan_entitlement, make_product, make_purchase, make_subscription, save


async def test_create_derives_the_code_from_the_name(client, admin_headers):
    response = await client.post("/api/tenants", json={"name": "Blue Books", "domain": "blue.example.org"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["code"] == "blue-books"


async def test_create_keeps_an_explicit_code(client, admin_headers):
    response = await client.post("/api/tenants", json={"code": "blue", "name": "Blue Books", "domain": "blue.example.org"}, headers=admin_headers)

    assert response.json()["code"] == "blue"


async def test_create_refuses_a_duplicated_code(client, tenant, admin_headers):
    response = await client.post("/api/tenants", json={"code": tenant.code, "name": "Other", "domain": "other.example.org"}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["errors"]["code"]


async def test_create_refuses_a_duplicated_domain(client, tenant, admin_headers):
    response = await client.post("/api/tenants", json={"code": "other", "name": "Other", "domain": tenant.domain}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["errors"]["domain"]


async def test_update_keeps_the_code_when_it_is_not_sent(client, tenant, admin_headers):
    response = await client.put(f"/api/tenants/{tenant.id}", json={"name": "Renamed"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["code"] == tenant.code
    assert response.json()["name"] == "Renamed"


async def test_update_refuses_the_domain_of_another_tenant(client, tenant, admin_headers):
    other = await client.post("/api/tenants", json={"name": "Other", "domain": "other.example.org"}, headers=admin_headers)

    response = await client.put(f"/api/tenants/{other.json()['id']}", json={"domain": tenant.domain}, headers=admin_headers)

    assert response.status_code == 409


async def test_delete_takes_everything_the_tenant_owns(client, db, tenant, admin_headers):
    await make_product(db, tenant)
    await make_content(db, tenant)
    await make_banner(db, tenant)

    response = await client.delete(f"/api/tenants/{tenant.id}", headers=admin_headers)

    assert response.status_code == 204
    assert (await client.get("/api/products", headers=admin_headers)).json()["count"] == 0
    assert (await client.get("/api/contents", headers=admin_headers)).json()["count"] == 0
    assert (await client.get("/api/banners", headers=admin_headers)).json()["count"] == 0


async def test_search_matches_the_code_and_the_name(client, tenant, admin_headers):
    assert (await client.get("/api/tenants?search=acm", headers=admin_headers)).json()["count"] == 1
    assert (await client.get("/api/tenants?search=nothing", headers=admin_headers)).json()["count"] == 0


async def test_filter_by_active(client, tenant, admin_headers):
    await client.post("/api/tenants", json={"name": "Off", "domain": "off.example.org", "active": False}, headers=admin_headers)

    assert (await client.get("/api/tenants?active=true", headers=admin_headers)).json()["count"] == 1
    assert (await client.get("/api/tenants?active=false", headers=admin_headers)).json()["count"] == 1


async def test_deleting_a_tenant_that_owns_the_whole_graph_takes_every_row_of_it(client, db, tenant, member, admin_headers):
    """A restricted reference fires the moment the order is wrong, and every one of these points at a row of another table."""
    product = await make_product(db, tenant)
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, product_id=product.id, target="handbook")

    subscription = await make_subscription(db, tenant, member, plan)
    await delivery_service.activate(db, subscription)

    integration = await make_integration(db, tenant)
    await make_external_product(db, integration, plan)
    await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-graph", payload={}, payload_hash="graph"))

    purchase = await make_purchase(db, tenant, member, product)
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID)

    await make_address(db, member)
    gallery = await make_gallery(db, tenant)
    await make_gallery_photo(db, gallery)
    await make_content(db, tenant)
    await make_banner(db, tenant)
    await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="graph-event", name="app_opened", params={}, occurred_at=now()))
    await system_log_service.record(db, tenant.id, member.id, LogLevel.INFO, LogCategory.ACCOUNT, "something happened", {})
    await db.commit()

    tenant_id = tenant.id

    assert (await client.delete(f"/api/tenants/{tenant.id}", headers=admin_headers)).status_code == 204

    db.expunge_all()

    assert await db.get(User, member.id) is None

    for model in (UserAddress, Subscription, SubscriptionBenefit, BenefitGrant, UserEntitlement, CreditTransaction, Purchase, UserProduct, Integration, ExternalProduct, WebhookEvent, Plan, Entitlement, Benefit, PlanEntitlement, Product, Gallery, GalleryPhoto, Content, Banner, AppEvent):
        assert await db.scalar(select(func.count()).select_from(model)) == 0, model.__name__

    # What belonged to the tenant went with it, and what an administrator did belongs to the administrator.
    assert await db.scalar(select(func.count()).select_from(SystemLog).where(SystemLog.tenant_id.is_not(None))) == 0
    assert (await db.scalar(select(SystemLog).where(SystemLog.category == LogCategory.ADMIN))).description.endswith(f"deleted tenants {tenant_id}")
