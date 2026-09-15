from fastapi import APIRouter, Query

from helpers import cache, idempotency
from helpers.auth import BrandAccount, CurrentBrand, CurrentUser, OptionalBrandAccount
from helpers.crud import RecordId, build_readonly_router, build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.i18n import current_locale
from helpers.idempotency import IdempotencyKey
from helpers.pagination import PAGE_SIZE, ListingLimit, ListingOffset, Page
from helpers.storage import storage
from schemas.checkout import CheckoutRequest, CheckoutResponse
from schemas.commerce import AccountProductListResponse, AccountProductSchema, AccountPurchaseSchema, CatalogProductSchema, ProductCreate, ProductListResponse, ProductSchema, ProductUpdate, PurchaseSchema, UserProductSchema, product_card
from services.checkout import checkout_service
from services.commerce import product_service, purchase_service, user_product_service

public_router = APIRouter(prefix="/commerce", tags=["commerce"])


@public_router.get("/products", response_model=ProductListResponse, summary="List what a tenant sells")
async def list_products(db: DatabaseSession, brand: CurrentBrand, user: OptionalBrandAccount, search: str | None = Query(None, max_length=128)):
    term = (search or "").strip() or None

    async def build():
        # What is kept is what travels, so a price that no store could write down never reaches the cache as one.
        return [product_card(product).model_dump(mode="json") for product in await product_service.list_reachable(db, brand.id, term)]

    # What is kept is the catalogue and never the ownership, because owning is of one account and the row is read by everybody.
    catalogue = await cache.answered(cache.search if term else cache.products, cache.named(surface="api", tenant=brand.id, language=current_locale.get(), search=term), build)
    owned = await user_product_service.owned_ids(db, user.id) if user is not None else set()

    return ProductListResponse(items=[CatalogProductSchema(**entry, owned=entry["id"] in owned) for entry in catalogue])


@public_router.post("/products/{slug}/checkout", response_model=CheckoutResponse, summary="Open a payment for one product")
async def buy_product(db: DatabaseSession, brand: CurrentBrand, user: BrandAccount, slug: str, payload: CheckoutRequest, idempotency_key: IdempotencyKey = None):
    """The purchase is written on this side before the buyer leaves, exactly as it is when the site sends them."""
    product = await product_service.find_reachable(db, brand.id, slug)

    if product is None:
        raise NotFoundError()

    async def work():
        return CheckoutResponse(url=await checkout_service.for_product(db, brand, user, product, payload.success_url, payload.cancel_url)).model_dump()

    return CheckoutResponse(**await idempotency.once(db, user, idempotency_key, "commerce-product-checkout", work))


@public_router.get("/products/{slug}", response_model=CatalogProductSchema, summary="Read one product by its slug")
async def read_product(db: DatabaseSession, brand: CurrentBrand, user: OptionalBrandAccount, slug: str):
    async def build():
        product = await product_service.find_reachable(db, brand.id, slug)

        if product is None:
            raise NotFoundError()

        return product_card(product).model_dump(mode="json")

    entry = await cache.answered(cache.products, cache.named(surface="api", tenant=brand.id, language=current_locale.get(), slug=slug), build)

    return CatalogProductSchema(**entry, owned=user is not None and await user_product_service.owned_by(db, user.id, entry["id"]))


account_router = APIRouter(prefix="/account", tags=["account"])


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
async def list_purchases(db: DatabaseSession, user: CurrentUser, limit: ListingLimit = PAGE_SIZE, offset: ListingOffset = 0):
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
