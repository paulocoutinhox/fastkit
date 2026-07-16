from email.message import EmailMessage as MimeMessage

from fastkit_mail.provider import EmailMessage, EmailProviderResult, ProviderHealth, ProviderStatus


def build_mime(message: EmailMessage) -> MimeMessage:
    mime = MimeMessage()
    mime["From"] = message.from_email
    mime["To"] = ", ".join(message.to)
    mime["Subject"] = message.subject

    if message.cc:
        mime["Cc"] = ", ".join(message.cc)

    if message.reply_to:
        mime["Reply-To"] = message.reply_to

    mime.set_content(message.text_body)
    mime.add_alternative(message.html_body, subtype="html")

    return mime


class SmtpEmailProvider:
    """Sends through an SMTP server such as a local MailCatcher, via aiosmtplib."""

    def __init__(self, host: str, port: int, username: str = "", password: str = "", use_tls: bool = False):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls

    async def send(self, message: EmailMessage) -> EmailProviderResult:
        import aiosmtplib

        mime = build_mime(message)

        try:
            await aiosmtplib.send(
                mime,
                hostname=self._host,
                port=self._port,
                username=self._username or None,
                password=self._password or None,
                use_tls=self._use_tls,
                recipients=[*message.to, *message.cc, *message.bcc],
            )

            return EmailProviderResult(success=True, message_id=mime.get("Message-ID"))
        except Exception as error:
            return EmailProviderResult(success=False, error=str(error))

    async def health(self) -> ProviderHealth:
        import aiosmtplib

        try:
            client = aiosmtplib.SMTP(hostname=self._host, port=self._port, use_tls=self._use_tls)
            await client.connect()
            await client.quit()

            return ProviderHealth(ProviderStatus.healthy)
        except Exception as error:
            return ProviderHealth(ProviderStatus.unavailable, detail=str(error))
