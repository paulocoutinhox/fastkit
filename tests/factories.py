import secrets
from decimal import Decimal
from uuid import uuid4

from enums.integration import Provider
from enums.subscription import BenefitCadence, BenefitType, ResumeDeliveryPolicy, SubscriptionStatus
from enums.user import UserAddressType
from helpers.dates import now
from models.account import Currency
from models.banner import Banner
from models.commerce import Product, Purchase
from models.content import Content, ContentCategory
from models.country import Country
from models.gallery import Gallery, GalleryPhoto
from models.integration import ExternalProduct, Integration
from models.language import Language
from models.subscription import Benefit, Entitlement, Plan, PlanEntitlement, Subscription
from models.tenant import Tenant
from models.upload import StoredFile
from models.user import UserAddress


async def save(db, instance):
    db.add(instance)
    await db.commit()

    return instance


async def make_language(db, **overrides):
    values = {"name": "English", "native_name": "English", "code_iso_639_1": "en", "code_iso_language": "en-us"} | overrides

    return await save(db, Language(**values))


async def make_country(db, **overrides):
    values = {"name": "United Kingdom", "code_iso_3166_1": "GB"} | overrides

    return await save(db, Country(**values))


async def make_tenant(db, **overrides):
    values = {"code": "other", "name": "Other", "domain": "other.acme.com", "meta": {}} | overrides

    return await save(db, Tenant(**values))


async def make_entitlement(db, tenant=None, **overrides):
    values = {"code": "member", "name": "Member", "tenant_id": tenant.id if tenant else None, "meta": {}} | overrides

    return await save(db, Entitlement(**values))


async def make_plan(db, tenant=None, **overrides):
    values = {"code": "monthly", "name": "Monthly", "tenant_id": tenant.id if tenant else None, "currency": "USD", "price": Decimal("19.90"), "resume_delivery_policy": ResumeDeliveryPolicy.SAME_CYCLE, "meta": {}} | overrides

    return await save(db, Plan(**values))


async def make_plan_entitlement(db, plan, entitlement, **overrides):
    values = {"plan_id": plan.id, "entitlement_id": entitlement.id, "meta": {}} | overrides

    return await save(db, PlanEntitlement(**values))


async def make_benefit(db, entitlement, **overrides):
    values = {"entitlement_id": entitlement.id, "type": BenefitType.ACCESS, "target": "member", "quantity": 1, "cadence": BenefitCadence.ON_ACTIVATION, "meta": {}} | overrides

    if values["type"] == BenefitType.CREDIT and not values.get("currency_id"):
        values["currency_id"] = (await make_currency(db)).id

    return await save(db, Benefit(**values))


async def make_subscription(db, tenant, user, plan, **overrides):
    values = {"tenant_id": tenant.id if tenant else None, "user_id": user.id, "plan_id": plan.id, "status": SubscriptionStatus.ACTIVE, "started_at": now(), "meta": {}} | overrides

    return await save(db, Subscription(**values))


async def make_content_category(db, **overrides):
    values = {"name": "Legal", "tag": "legal"} | overrides

    return await save(db, ContentCategory(**values))


async def make_content(db, tenant=None, **overrides):
    values = {"title": "Terms", "tag": "terms", "content": "<p>Terms</p>", "tenant_id": tenant.id if tenant else None, "meta": {}} | overrides

    return await save(db, Content(**values))


async def make_banner(db, tenant=None, **overrides):
    values = {"title": "Promo", "position": 0, "tenant_id": tenant.id if tenant else None, "meta": {}} | overrides

    return await save(db, Banner(**values))


async def make_gallery(db, tenant=None, **overrides):
    values = {"title": "Office", "tag": "office", "position": 0, "tenant_id": tenant.id if tenant else None, "meta": {}} | overrides

    return await save(db, Gallery(**values))


async def make_gallery_photo(db, gallery, **overrides):
    values = {"gallery_id": gallery.id, "image": f"images/gallery/2026/08/18/{secrets.token_hex(4)}.webp", "caption": "Reception", "position": 0} | overrides

    return await save(db, GalleryPhoto(**values))


async def make_stored_file(db, purpose, folder: str, extension: str = "webp") -> str:
    """A file written down the way the upload service writes one, because only what this application wrote down is what it ever deletes."""
    drawn = str(uuid4())
    key = f"{folder}/2026/08/19/{drawn}.{extension}"

    await save(db, StoredFile(uuid=drawn, key=key, purpose=purpose, size=1))

    return key


async def make_product(db, tenant=None, **overrides):
    values = {"name": "Handbook", "slug": f"handbook-{secrets.token_hex(4)}", "tenant_id": tenant.id if tenant else None, "currency": "USD", "price": Decimal("19.90"), "credits": 0, "position": 0, "meta": {}} | overrides

    return await save(db, Product(**values))


async def make_purchase(db, tenant, user, product, **overrides):
    values = {"tenant_id": tenant.id if tenant else None, "user_id": user.id, "product_id": product.id, "currency": product.currency, "price": product.price, "meta": {}} | overrides

    return await save(db, Purchase(**values))


async def make_address(db, user, **overrides):
    values = {"user_id": user.id, "type": UserAddressType.MAIN, "line1": "221B Baker Street", "city": "London", "state": "London", "postal_code": "NW16XE", "country_code": "GB", "meta": {}} | overrides

    return await save(db, UserAddress(**values))


async def make_integration(db, tenant=None, **overrides):
    values = {"tenant_id": tenant.id if tenant else None, "provider": Provider.STRIPE, "webhook_key": secrets.token_urlsafe(16), "meta": {}} | overrides

    return await save(db, Integration(**values))


async def make_external_product(db, integration, plan, **overrides):
    values = {"integration_id": integration.id, "plan_id": plan.id, "external_id": f"price_{secrets.token_hex(4)}", "meta": {}} | overrides

    return await save(db, ExternalProduct(**values))


async def make_currency(db, tenant=None, **overrides):
    values = {"code": f"coin-{secrets.token_hex(3)}", "name": "Coins", "symbol": "¢", "tenant_id": tenant.id if tenant else None, "position": 0, "meta": {}} | overrides

    return await save(db, Currency(**values))
