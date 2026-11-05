from datetime import datetime

from enums.newsletter_status import NewsletterStatus
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class NewsletterSubscriptionSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    email: str
    locale: str
    status: NewsletterStatus
    settled_at: datetime | None
