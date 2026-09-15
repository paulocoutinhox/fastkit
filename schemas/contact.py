from pydantic import EmailStr, Field

from schemas.auth import Challenged


class ContactRequest(Challenged):
    """What somebody writes to the operator of a brand, from the site or from an application."""

    name: str = Field(min_length=2, max_length=128)
    email: EmailStr = Field(max_length=255)
    message: str = Field(min_length=10, max_length=4000)
