from fastapi import APIRouter, Request, status
from pydantic import EmailStr, Field

from helpers import captcha
from helpers.auth import CurrentBrand
from helpers.db import DatabaseSession
from helpers.errors import ValidationError
from schemas.common import BaseSchema
from services.contact import contact_service

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseSchema):
    name: str = Field(min_length=2, max_length=128)
    email: EmailStr = Field(max_length=255)
    message: str = Field(min_length=10, max_length=4000)
    captcha_answer: str | None = Field(None, max_length=64)
    captcha_token: str | None = Field(None, max_length=512)


@router.post("", status_code=status.HTTP_204_NO_CONTENT, summary="Write to the operator of a tenant")
async def send(request: Request, db: DatabaseSession, brand: CurrentBrand, payload: ContactRequest):
    """A form anybody may send is a form anybody may flood, so it carries the same challenge the site draws."""
    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    await contact_service.send(db, brand, payload.name, payload.email, payload.message)
