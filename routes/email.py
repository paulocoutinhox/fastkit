from helpers.crud import build_readonly_router
from schemas.outbound_email_schema import OutboundEmailSchema
from services.outbound_email_service import outbound_email_service

router = build_readonly_router(outbound_email_service, OutboundEmailSchema, "/outbound-emails", "outbound emails")
