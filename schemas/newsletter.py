from datetime import datetime

from pydantic import EmailStr, Field

from enums.newsletter import NewsletterStatus
from schemas.auth import Challenged
from schemas.common import TimestampSchema
from schemas.tenant import TenantReference


class NewsletterSubscriptionSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    email: str
    locale: str
    status: NewsletterStatus
    settled_at: datetime | None


class NewsletterRequest(Challenged):
    """An address asking to receive, from the site or from an application."""

    email: EmailStr = Field(max_length=320)
