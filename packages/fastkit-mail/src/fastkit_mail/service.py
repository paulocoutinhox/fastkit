import logging
from datetime import datetime, timezone

from fastkit_core.resilience import CircuitBreaker
from fastkit_mail.errors import SEND_FAILED
from fastkit_mail.models import DeliveryStatus, EmailDelivery
from fastkit_mail.provider import EmailMessage, EmailProviderResult
from fastkit_mail.templates import MailTemplateRenderer, RenderedEmail

logger = logging.getLogger("fastkit.mail")


class MailService:
    """Renders templates, persists an EmailDelivery and sends through the configured provider."""

    def __init__(self, session_factory, renderer: MailTemplateRenderer, provider, provider_name: str, default_from: str, clock=None, breaker: CircuitBreaker | None = None):
        self._session_factory = session_factory
        self._renderer = renderer
        self._provider = provider
        self._provider_name = provider_name
        self._default_from = default_from
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._breaker = breaker or CircuitBreaker()

    async def _send(self, message: EmailMessage) -> EmailProviderResult:
        if not self._breaker.allow():
            return EmailProviderResult(success=False, error="mail provider circuit is open")

        try:
            result = await self._provider.send(message)
        except Exception as error:
            self._breaker.record_failure()
            logger.warning("mail provider %s raised while sending: %s", self._provider_name, error)

            return EmailProviderResult(success=False, error=str(error))

        if result.success:
            self._breaker.record_success()
        else:
            self._breaker.record_failure()

        return result

    def preview(self, template_key: str, context: dict, locale: str = "en") -> RenderedEmail:
        return self._renderer.render(template_key, context, locale)

    async def send_template(self, template_key: str, to: list[str], context: dict, locale: str = "en", from_email: str | None = None, tenant_id: int | None = None) -> EmailDelivery:
        rendered = self._renderer.render(template_key, context, locale)

        delivery = EmailDelivery(
            tenant_id=tenant_id,
            provider=self._provider_name,
            template_key=template_key,
            template_path=rendered.template_path,
            locale=locale,
            from_email=from_email or self._default_from,
            to=to,
            subject=rendered.subject,
            html_body=rendered.html_body,
            text_body=rendered.text_body,
        )

        async with self._session_factory() as session:
            session.add(delivery)
            await session.commit()
            await session.refresh(delivery)

        return await self.deliver(delivery.id)

    async def deliver(self, delivery_id) -> EmailDelivery:
        async with self._session_factory() as session:
            delivery = await session.get(EmailDelivery, delivery_id)
            delivery.status = DeliveryStatus.sending.value
            delivery.attempt_count += 1
            await session.commit()

            message = EmailMessage(
                to=delivery.to,
                subject=delivery.subject,
                html_body=delivery.html_body,
                text_body=delivery.text_body,
                from_email=delivery.from_email,
                cc=delivery.cc or [],
                bcc=delivery.bcc or [],
                reply_to=delivery.reply_to,
            )

            result = await self._send(message)

            if result.success:
                delivery.status = DeliveryStatus.sent.value
                delivery.provider_message_id = result.message_id
                delivery.sent_at = self._clock()
            elif delivery.attempt_count >= delivery.max_attempts:
                delivery.status = DeliveryStatus.failed.value
                delivery.failed_at = self._clock()
                delivery.last_error_code = SEND_FAILED.code
                delivery.last_error_message = result.error
            else:
                delivery.status = DeliveryStatus.retrying.value
                delivery.last_error_code = SEND_FAILED.code
                delivery.last_error_message = result.error

            await session.commit()
            await session.refresh(delivery)

            return delivery

    async def retry(self, delivery_id) -> EmailDelivery:
        return await self.deliver(delivery_id)
