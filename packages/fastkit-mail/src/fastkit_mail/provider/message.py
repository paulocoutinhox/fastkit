from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html_body: str
    text_body: str
    from_email: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None
