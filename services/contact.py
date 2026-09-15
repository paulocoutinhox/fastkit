from sqlalchemy.ext.asyncio import AsyncSession

from helpers.brand import Brand
from helpers.i18n import translate
from helpers.settings import settings
from services.email import email_service


class ContactService:
    """What somebody writes to the operator, which is a message in the queue and never a call dialled inside the request."""

    async def send(self, db: AsyncSession, brand: Brand, name: str, email: str, message: str) -> None:
        """The sender is the address of the system, so the answer of the operator is carried back by `reply_to`."""
        await email_service.queue(db, brand.id, brand.email_contact or settings.email.from_address, translate("email.contact-subject"), "contact", reply_to=email, name=name, email=email, message=message)


contact_service = ContactService()
