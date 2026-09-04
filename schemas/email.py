from datetime import datetime

from enums.email import OutboundEmailStatus
from schemas.common import TimestampSchema
from schemas.tenant import TenantReference


class OutboundEmailSchema(TimestampSchema):
    """What a message is and how it went, and never the context it was written from: a reset mail carries the credential in it."""

    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    to_address: str
    reply_to: str | None
    subject: str
    template: str
    locale: str
    status: OutboundEmailStatus
    attempts: int
    error_code: str | None
    error_message: str | None
    sent_at: datetime | None
