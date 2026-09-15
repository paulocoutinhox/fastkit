from fastapi import APIRouter
from starlette.responses import RedirectResponse

from enums.commerce import PurchaseStatus
from helpers.db import DatabaseSession
from helpers.errors import AppError
from helpers.site import PageNotFound, notice, redirect, render
from routes.site.base import CsrfToken, CurrentPage, PrivatePage, guard
from services.checkout import checkout_service
from services.commerce import product_service, purchase_service
from services.subscription import plan_service

router = APIRouter(include_in_schema=False)


def endpoints(page) -> tuple[str, str]:
    """Where a gateway sends the buyer back, which is the site of the brand and never the host this request happened to name."""
    return page.brand.address("/checkout/success"), page.brand.address("/checkout/error")


@router.post("/checkout/product/{slug}")
async def buy_product(page: PrivatePage, db: DatabaseSession, slug: str, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    product = await product_service.find_reachable(db, page.brand.id, slug)

    if product is None:
        raise PageNotFound()

    success_url, cancel_url = endpoints(page)

    try:
        return RedirectResponse(await checkout_service.for_product(db, page.brand, page.user, product, success_url, cancel_url), status_code=303)
    except AppError as refused:
        return redirect(f"/products/{slug}", [notice(refused.code, "error")])


@router.post("/checkout/plan/{code}")
async def subscribe(page: PrivatePage, db: DatabaseSession, code: str, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    plan = next((offer for offer in await plan_service.list_offered(db, page.brand.id, page.language) if offer.code == code), None)

    if plan is None:
        raise PageNotFound()

    success_url, cancel_url = endpoints(page)

    try:
        return RedirectResponse(await checkout_service.for_plan(db, page.brand, page.user, plan, success_url, cancel_url), status_code=303)
    except AppError as refused:
        return redirect("/plans", [notice(refused.code, "error")])


ARRIVED = ("paid", "site.checkout-success", "site.checkout-success-lead")

ON_ITS_WAY = ("pending", "site.checkout-pending", "site.checkout-pending-lead")

REFUSED = ("refused", "site.checkout-error", "site.checkout-error-lead")

OUTCOMES = {PurchaseStatus.PENDING: ON_ITS_WAY, PurchaseStatus.PAID: ARRIVED, PurchaseStatus.CANCELED: REFUSED, PurchaseStatus.FAILED: REFUSED, PurchaseStatus.REFUNDED: REFUSED, PurchaseStatus.CHARGED_BACK: REFUSED}


def drawn(settled: tuple[str, str, str], record) -> dict:
    """Trying again starts where the buyer left from, which is the product a purchase was for and the plans where a subscription writes none."""
    outcome, title_key, lead_key = settled

    return {"outcome": outcome, "title_key": title_key, "lead_key": lead_key, "again": f"/products/{record.product.slug}" if record else "/plans"}


async def mine(db, page, reference: str):
    """The purchase the gateway sent the buyer back about, when it is this account's."""
    if not reference or page.user is None:
        return None

    record = await purchase_service.find_by_reference(db, reference)

    return record if record is not None and record.user_id == page.user.id else None


@router.get("/checkout/success")
async def paid(page: CurrentPage, db: DatabaseSession, purchase: str = ""):
    """A card is charged before the buyer is back and a boleto is not, so the page reads the row instead of assuming, and a subscription writes no purchase of ours to read."""
    record = await mine(db, page, purchase)

    return render(page, "checkout/result.html", drawn(ARRIVED if record is None else OUTCOMES[record.status], record))


@router.get("/checkout/error")
async def cancelled(page: CurrentPage, db: DatabaseSession, purchase: str = ""):
    return render(page, "checkout/result.html", drawn(REFUSED, await mine(db, page, purchase)))
