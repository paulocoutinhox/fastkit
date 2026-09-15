from schemas.common import BaseSchema, ReturnUrl


class CheckoutRequest(BaseSchema):
    """Where the gateway sends the buyer back to, which an application names because only it knows its own way home."""

    success_url: ReturnUrl
    cancel_url: ReturnUrl


class CheckoutResponse(BaseSchema):
    url: str
