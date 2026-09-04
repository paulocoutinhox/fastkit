from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.commerce import PurchaseStatus
from enums.integration import Provider
from helpers import remote
from helpers.brand import Brand
from helpers.errors import AppError
from helpers.money import minor_units
from models.commerce import Product
from models.integration import ExternalProduct, Integration
from models.subscription import Plan
from models.user import User
from services.commerce import commerce_service
from services.integration import integration_service

STRIPE_SESSIONS = "https://api.stripe.com/v1/checkout/sessions"

TIMEOUT = 15.0


class CheckoutService:
    """What sends a buyer to a gateway, and the row this side writes before they ever leave."""

    def naming(self, url: str, reference: str) -> str:
        """The page the buyer lands on reads the row itself, because a method that settles days later comes back unpaid."""
        parts = urlsplit(url)
        query = urlencode(dict(parse_qsl(parts.query)) | {"purchase": reference})

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
            "cancel_url": cancel_url,
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

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            answer = await client.post(STRIPE_SESSIONS, data=form, headers={"Authorization": f"Bearer {secret}"})

        if answer.status_code != httpx.codes.OK:
            raise AppError("error.checkout-refused")

        opened = remote.body_of(answer).get("url")

        if not opened:
            raise AppError("error.checkout-refused")

        return opened


checkout_service = CheckoutService()
