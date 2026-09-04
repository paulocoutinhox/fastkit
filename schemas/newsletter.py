from datetime import datetime

from enums.newsletter import NewsletterStatus
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
