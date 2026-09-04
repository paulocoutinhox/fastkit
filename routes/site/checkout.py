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
        return redirect(page, f"/products/{slug}", [notice(refused.code, "error")])


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
        return redirect(page, "/plans", [notice(refused.code, "error")])


ARRIVED = ("paid", "site.checkout-success", "site.checkout-success-lead")

ON_ITS_WAY = ("pending", "site.checkout-pending", "site.checkout-pending-lead")

REFUSED = ("refused", "site.checkout-error", "site.checkout-error-lead")

OUTCOMES = {PurchaseStatus.PENDING: ON_ITS_WAY, PurchaseStatus.ANALYSIS: ON_ITS_WAY, PurchaseStatus.PAID: ARRIVED}


def drawn(settled: tuple[str, str, str]) -> dict:
    outcome, title_key, lead_key = settled

    return {"outcome": outcome, "title_key": title_key, "lead_key": lead_key}


@router.get("/checkout/success")
async def paid(page: CurrentPage, db: DatabaseSession, purchase: str = ""):
    """A card is charged before the buyer is back and a boleto is not, so the page reads the row instead of assuming."""
    return render(page, "checkout/result.html", drawn(await settled_as(db, page, purchase)))


async def settled_as(db, page, reference: str) -> tuple[str, str, str]:
    """A subscription writes no purchase of ours, so a landing with nothing to read is the success the gateway sent it to."""
    if not reference or page.user is None:
        return ARRIVED

    record = await purchase_service.find_by_reference(db, reference)

    if record is None or record.user_id != page.user.id:
        return ARRIVED

    return OUTCOMES.get(record.status, REFUSED)


@router.get("/checkout/error")
async def cancelled(page: CurrentPage):
    return render(page, "checkout/result.html", drawn(REFUSED))
