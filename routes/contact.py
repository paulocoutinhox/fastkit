from fastapi import APIRouter, Request, status

from helpers import captcha
from helpers.auth import CurrentBrand
from helpers.db import DatabaseSession
from helpers.errors import ValidationError
from schemas.contact import ContactRequest
from services.contact import contact_service

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT, summary="Write to the operator of a tenant")
async def send(request: Request, db: DatabaseSession, brand: CurrentBrand, payload: ContactRequest):
    """A form anybody may send is a form anybody may flood, so it carries the same challenge the site draws."""
    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    await contact_service.send(db, brand, payload.name, payload.email, payload.message)
