from pydantic import EmailStr, Field

from schemas.challenged import Challenged


class NewsletterRequest(Challenged):
    """An address asking to receive, from the site or from an application."""

    email: EmailStr = Field(max_length=320)
