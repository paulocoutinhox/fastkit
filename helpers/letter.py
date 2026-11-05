"""One message as every service that carries mail asks for it, which is the parts and never an envelope already sealed."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Letter:
    # The name a reader sees the letter come from, which is the brand it was written under and never the account that carries it.
    sender: str
    to: str
    subject: str
    html: str
    reply_to: str | None = None
