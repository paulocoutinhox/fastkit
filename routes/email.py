from helpers.crud import build_readonly_router
from schemas.email import OutboundEmailSchema
from services.email import outbound_email_service

router = build_readonly_router(outbound_email_service, OutboundEmailSchema, "/outbound-emails", "outbound emails")
