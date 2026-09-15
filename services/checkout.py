from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.commerce import PurchaseStatus
from enums.integration import Provider
from enums.subscription import CLOSED_SUBSCRIPTION_STATUSES
from helpers import remote
from helpers.brand import Brand
from helpers.errors import AppError, ConflictError
from helpers.money import minor_units
from models.commerce import Product
from models.integration import ExternalProduct, Integration
from models.subscription import Plan, Subscription
from models.user import User
from services.commerce import commerce_service
from services.gateway import StripeProvider
from services.integration import integration_service

STRIPE_SESSIONS = f"{StripeProvider.API}/checkout/sessions"

TIMEOUT = 15.0


class CheckoutService:
    """What sends a buyer to a gateway, and the row this side writes before they ever leave."""

    def naming(self, url: str, reference: str) -> str:
        """The page the buyer lands on reads the row itself, because a method that settles days later comes back unpaid."""
        parts = urlsplit(url)

        # The query of the caller is kept exactly as written, because Stripe fills a literal {CHECKOUT_SESSION_ID} and an app may repeat a key or leave one blank.
        query = "&".join(part for part in (parts.query, urlencode({"purchase": reference})) if part)

        return urlunsplit(parts._replace(query=query))

    async def gateway_of(self, db: AsyncSession, brand: Brand) -> Integration:
        integration = await db.scalar(select(Integration).where(Integration.tenant_id == brand.id, Integration.provider == Provider.STRIPE, Integration.active.is_(True)))

        if integration is None:
            raise AppError("error.checkout-unavailable")

        return integration

    async def price_of(self, db: AsyncSession, integration: Integration, plan: Plan) -> str:
        """A subscription is sold by the price the gateway knows, and a plan nothing maps cannot be bought."""
        external_id = await db.scalar(select(ExternalProduct.external_id).where(ExternalProduct.integration_id == integration.id, ExternalProduct.plan_id == plan.id, ExternalProduct.active.is_(True)))

        if not external_id:
            raise AppError("error.checkout-unavailable")

        return external_id

    async def for_product(self, db: AsyncSession, brand: Brand, user: User, product: Product, success_url: str, cancel_url: str) -> str:
        """The purchase exists before the buyer leaves, because what the gateway echoes back has to name a row this side already wrote."""
        integration = await self.gateway_of(db, brand)
        purchase = await commerce_service.open_purchase(db, brand, user, product, integration.id)

        form = {
            "mode": "payment",
            "client_reference_id": purchase.reference,
            "metadata[account_token]": user.token,
            "success_url": self.naming(success_url, purchase.reference),
            "cancel_url": self.naming(cancel_url, purchase.reference),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": product.currency.lower(),
            "line_items[0][price_data][unit_amount]": str(minor_units(product.price, product.currency)),
            "line_items[0][price_data][product_data][name]": product.name,
        }

        # No session opened means the buyer never left, so the row this side wrote is closed instead of waiting for a notice nobody will send.
        try:
            return await self.open_session(integration, form)
        except AppError:
            await commerce_service.settle_purchase(db, purchase, PurchaseStatus.FAILED)

            raise

    async def for_plan(self, db: AsyncSession, brand: Brand, user: User, plan: Plan, success_url: str, cancel_url: str) -> str:
        integration = await self.gateway_of(db, brand)
        price = await self.price_of(db, integration, plan)

        # One account holds one row per product of a gateway, so a second subscription to it while the first is not closed, a paused one included, would be charged and carried by nobody.
        if await db.scalar(select(Subscription.id).where(Subscription.user_id == user.id, Subscription.integration_id == integration.id, Subscription.plan_id == plan.id, Subscription.status.not_in(CLOSED_SUBSCRIPTION_STATUSES))) is not None:
            raise ConflictError("error.plan-already-subscribed")

        form = {
            "mode": "subscription",
            "metadata[account_token]": user.token,
            # The token is put on the subscription too, because what the gateway reports later is that object and not this session.
            "subscription_data[metadata][account_token]": user.token,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][quantity]": "1",
            "line_items[0][price]": price,
        }

        return await self.open_session(integration, form)

    async def open_session(self, integration: Integration, form: dict) -> str:
        secret = integration_service.read_secret(integration)

        if not secret:
            raise AppError("error.checkout-unavailable")

        # A gateway that did not answer opened no session, which is the refusal the purchase is closed on.
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                answer = await client.post(STRIPE_SESSIONS, data=form, headers={"Authorization": f"Bearer {secret}"})
        except httpx.HTTPError as error:
            raise AppError("error.checkout-refused") from error

        if answer.status_code != httpx.codes.OK:
            raise AppError("error.checkout-refused")

        opened = remote.body_of(answer).get("url")

        if not opened:
            raise AppError("error.checkout-refused")

        return opened


checkout_service = CheckoutService()
