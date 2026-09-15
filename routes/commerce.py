from fastapi import APIRouter, Query

from helpers import cache, idempotency
from helpers.auth import CurrentBrand, CurrentUser, OptionalUser
from helpers.crud import RecordId, build_readonly_router, build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.i18n import current_locale
from helpers.idempotency import IdempotencyKey
from helpers.pagination import ListingLimit, ListingOffset, Page
from helpers.storage import storage
from schemas.commerce import AccountProductSchema, AccountPurchaseSchema, CatalogEntrySchema, CatalogProductSchema, ProductCreate, ProductSchema, ProductUpdate, PurchaseSchema, UserProductSchema
from schemas.common import BaseSchema, ReturnUrl
from services.checkout import checkout_service
from services.commerce import product_service, purchase_service, user_product_service

public_router = APIRouter(prefix="/commerce", tags=["commerce"])


class ProductListResponse(BaseSchema):
    items: list[CatalogProductSchema]


def catalogued(product) -> dict:
    """What is kept is what travels, so a price that no store could write down never reaches the cache as one."""
    return CatalogEntrySchema(id=product.id, uuid=product.uuid, name=product.name, slug=product.slug, description=product.description, image_url=storage.url(product.image) if product.image else None, currency=product.currency, price=product.price, credits=product.credits, featured=product.featured).model_dump(
        mode="json"
    )


async def owned_ids(db, user) -> set[int]:
    if user is None:
        return set()

    return {held.product_id for held in await user_product_service.list_for_user(db, user.id)}


@public_router.get("/products", response_model=ProductListResponse, summary="List what a tenant sells")
async def list_products(db: DatabaseSession, brand: CurrentBrand, user: OptionalUser, search: str | None = Query(None, max_length=128)):
    term = (search or "").strip() or None

    async def build():
        return [catalogued(product) for product in await product_service.list_reachable(db, brand.id, term)]

    # What is kept is the catalogue and never the ownership, because owning is of one account and the row is read by everybody.
    catalogue = await cache.answered(cache.search if term else cache.products, cache.named(surface="api", tenant=brand.id, language=current_locale.get(), search=term), build)
    owned = await owned_ids(db, user)

    return ProductListResponse(items=[CatalogProductSchema(**entry, owned=entry["id"] in owned) for entry in catalogue])


class CheckoutRequest(BaseSchema):
    """Where the gateway sends the buyer back to, which an application names because only it knows its own way home."""

    success_url: ReturnUrl
    cancel_url: ReturnUrl


class CheckoutResponse(BaseSchema):
    url: str


@public_router.post("/products/{slug}/checkout", response_model=CheckoutResponse, summary="Open a payment for one product")
async def buy_product(db: DatabaseSession, brand: CurrentBrand, user: CurrentUser, slug: str, payload: CheckoutRequest, idempotency_key: IdempotencyKey = None):
    """The purchase is written on this side before the buyer leaves, exactly as it is when the site sends them."""
    product = await product_service.find_reachable(db, brand.id, slug)

    if product is None:
        raise NotFoundError()

    named, kept = await idempotency.claim(db, user, idempotency_key, "commerce-product-checkout")

    if kept is not None:
        return CheckoutResponse(**kept)

    answer = CheckoutResponse(url=await checkout_service.for_product(db, brand, user, product, payload.success_url, payload.cancel_url))
    await idempotency.settle(db, named, answer.model_dump())

    return answer


@public_router.get("/products/{slug}", response_model=CatalogProductSchema, summary="Read one product by its slug")
async def read_product(db: DatabaseSession, brand: CurrentBrand, user: OptionalUser, slug: str):
    async def build():
        product = await product_service.find_reachable(db, brand.id, slug)

        if product is None:
            raise NotFoundError()

        return catalogued(product)

    entry = await cache.answered(cache.products, cache.named(surface="api", tenant=brand.id, language=current_locale.get(), slug=slug), build)

    return CatalogProductSchema(**entry, owned=entry["id"] in await owned_ids(db, user))


account_router = APIRouter(prefix="/account", tags=["account"])


class AccountProductListResponse(BaseSchema):
    items: list[AccountProductSchema]


@account_router.get("/products", response_model=AccountProductListResponse, summary="List what the signed in account owns")
async def list_owned(db: DatabaseSession, user: CurrentUser):
    """The address of the file is built here and nowhere else, because this is the one surface that already knows the caller owns it."""
    held = await user_product_service.list_for_user(db, user.id)

    return AccountProductListResponse(
        items=[
            AccountProductSchema(
                id=row.product.id, uuid=row.product.uuid, name=row.product.name, slug=row.product.slug, description=row.product.description, image_url=storage.url(row.product.image) if row.product.image else None, file_url=storage.url(row.product.file) if row.product.file else None, granted_at=row.granted_at
            )
            for row in held
        ]
    )


@account_router.get("/purchases", response_model=Page[AccountPurchaseSchema], summary="List what the signed in account paid for")
async def list_purchases(db: DatabaseSession, user: CurrentUser, limit: ListingLimit = 50, offset: ListingOffset = 0):
    total, items = await purchase_service.list_for_user(db, user.id, limit, offset)

    return Page[AccountPurchaseSchema](count=total, limit=limit, offset=offset, items=[AccountPurchaseSchema.model_validate(item) for item in items])


@account_router.get("/purchases/{purchase_id}", response_model=AccountPurchaseSchema, summary="Read one purchase of the signed in account")
async def read_purchase(db: DatabaseSession, user: CurrentUser, purchase_id: RecordId):
    """A purchase of somebody else is one that does not exist here, because an identifier a client chose is never a permission."""
    held = await purchase_service.find_for_user(db, user.id, purchase_id)

    if held is None:
        raise NotFoundError()

    return AccountPurchaseSchema.model_validate(held)


router = build_router(product_service, ProductSchema, ProductCreate, ProductUpdate, "/products", "products")
purchase_router = build_readonly_router(purchase_service, PurchaseSchema, "/purchases", "purchases")
user_product_router = build_readonly_router(user_product_service, UserProductSchema, "/user-products", "user products")
