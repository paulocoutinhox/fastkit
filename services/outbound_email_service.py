from models.outbound_email import OutboundEmail
from services.crud_service import CrudService


class OutboundEmailService(CrudService):
    """The queue an operator reads when somebody says the message never arrived."""

    model = OutboundEmail
    search_fields = ("to_address", "template")
    filter_fields = ("tenant_id", "status", "template")
    ordering_fields = ("id", "status", "attempts", "sent_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant",)
    label_fields = ("subject",)


outbound_email_service = OutboundEmailService()
