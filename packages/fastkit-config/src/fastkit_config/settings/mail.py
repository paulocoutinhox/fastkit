from pydantic import BaseModel


class MailSettings(BaseModel):
    provider: str = "smtp"
    host: str = "localhost"
    port: int = 1025
    username: str = ""
    password: str = ""
    use_tls: bool = False
    default_from: str = "no-reply@fastkit.local"
