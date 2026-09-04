from typing import Callable

from fastapi import APIRouter, Request, status
from pydantic import EmailStr, Field

from enums.newsletter import NewsletterStatus
from helpers import captcha
from helpers.auth import CurrentBrand
from helpers.brand import Brand
from helpers.crud import build_readonly_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError, ValidationError
from schemas.common import BaseSchema
from schemas.newsletter import NewsletterSubscriptionSchema
from services.newsletter import newsletter_subscription_service

public_router = APIRouter(prefix="/newsletter", tags=["newsletter"])


class NewsletterRequest(BaseSchema):
    email: EmailStr = Field(max_length=320)
    captcha_answer: str | None = Field(None, max_length=64)
    captcha_token: str | None = Field(None, max_length=512)


def confirmation_link(brand: Brand) -> Callable[[str], str]:
    """The link is clicked in a mail client and never inside the application, so it points at the site of the brand."""
    return lambda token: brand.address(f"/newsletter/confirm/{token}")


@public_router.post("", status_code=status.HTTP_204_NO_CONTENT, summary="Ask to hear from a tenant")
async def subscribe(request: Request, db: DatabaseSession, brand: CurrentBrand, payload: NewsletterRequest):
    """The address is written down as pending and hears nothing until it answers the confirmation."""
    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    await newsletter_subscription_service.subscribe(db, brand, payload.email, confirmation_link(brand))


@public_router.post("/confirm/{token}", status_code=status.HTTP_204_NO_CONTENT, summary="Confirm a subscription")
async def confirm(db: DatabaseSession, brand: CurrentBrand, token: str):
    await settle(db, brand, token, NewsletterStatus.CONFIRMED)


@public_router.post("/unsubscribe/{token}", status_code=status.HTTP_204_NO_CONTENT, summary="Leave a newsletter")
async def unsubscribe(db: DatabaseSession, brand: CurrentBrand, token: str):
    await settle(db, brand, token, NewsletterStatus.UNSUBSCRIBED)


async def settle(db, brand: Brand, token: str, status_wanted: NewsletterStatus) -> None:
    """The token is the address proving it is the address, so one that names nothing is one that does not exist."""
    found = await newsletter_subscription_service.find_by_token(db, token)

    if found is None or found.tenant_id != brand.id:
        raise NotFoundError()

    await newsletter_subscription_service.settle(db, found, status_wanted)


router = build_readonly_router(newsletter_subscription_service, NewsletterSubscriptionSchema, "/newsletter-subscriptions", "newsletter-subscriptions")
