from pydantic import BaseModel

from enums.email_provider import EmailProvider


class EmailSettings(BaseModel):
    """Which service carries the mail of this environment, and the account it sends through."""

    # A message is sent, and printing it instead is the machine of whoever develops saying so: an environment that forgot to configure mail writes every recovery token into its log.
    provider: EmailProvider = EmailProvider.SMTP
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_address: str = "no-reply@localhost"
