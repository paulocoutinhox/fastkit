import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from fastkit_webhooks.models import WebhookEvent, WebhookStatus
from fastkit_webhooks.provider import RawWebhookRequest


class WebhookRegistry:
    def __init__(self):
        self._providers: dict[str, object] = {}

    def register(self, provider) -> None:
        if provider.name in self._providers:
            raise ValueError(
                f"webhook provider '{provider.name}' is already registered"
            )

        self._providers[provider.name] = provider

    def get(self, name: str):
        provider = self._providers.get(name)

        if provider is None:
            raise KeyError(f"webhook provider '{name}' is not registered")

        return provider


class WebhookService:
    """Verifies, persists and idempotently processes inbound webhooks."""

    def __init__(self, database, registry: WebhookRegistry, clock=None):
        self._database = database
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def receive(
        self, provider_name: str, headers: dict, body: bytes
    ) -> tuple[WebhookEvent, bool]:
        provider = self._registry.get(provider_name)
        request = RawWebhookRequest(headers=headers, body=body)

        verification = await provider.verify(request)

        if not verification.valid:
            rejected = await self._store_rejected(
                provider_name, request, verification.reason
            )

            return rejected, True

        try:
            normalized = await provider.normalize(request)
        except (ValueError, KeyError) as error:
            rejected = await self._store_rejected(
                provider_name, request, f"malformed payload: {error}"
            )

            return rejected, True

        return await self._store_valid(provider_name, request, normalized)

    async def _store_valid(
        self, provider_name, request, normalized
    ) -> tuple[WebhookEvent, bool]:
        event = WebhookEvent(
            provider=provider_name,
            provider_account_id=normalized.provider_account_id,
            external_event_id=normalized.external_event_id,
            event_type=normalized.event_type,
            signature_valid=True,
            headers=dict(request.headers),
            raw_body=request.body,
            payload=normalized.payload,
            status=WebhookStatus.received.value,
            received_at=self._clock(),
        )

        async with self._database.session_factory() as session:
            session.add(event)

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                duplicate = (
                    await session.execute(
                        select(WebhookEvent).where(
                            WebhookEvent.provider == provider_name,
                            WebhookEvent.provider_account_id
                            == normalized.provider_account_id,
                            WebhookEvent.external_event_id
                            == normalized.external_event_id,
                        )
                    )
                ).scalar_one_or_none()

                return duplicate, False

            await session.refresh(event)

            return event, True

    async def _store_rejected(self, provider_name, request, reason) -> WebhookEvent:
        external_id = hashlib.sha256(request.body).hexdigest()[:32]

        async with self._database.session_factory() as session:
            event = WebhookEvent(
                provider=provider_name,
                provider_account_id="unknown",
                external_event_id=external_id,
                event_type="rejected",
                signature_valid=False,
                headers=dict(request.headers),
                raw_body=request.body,
                status=WebhookStatus.rejected.value,
                received_at=self._clock(),
                last_error_code="webhook.invalid_signature",
                last_error_message=reason,
            )
            session.add(event)

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()

                return (
                    await session.execute(
                        select(WebhookEvent).where(
                            WebhookEvent.provider == provider_name,
                            WebhookEvent.provider_account_id == "unknown",
                            WebhookEvent.external_event_id == external_id,
                        )
                    )
                ).scalar_one()

            await session.refresh(event)

            return event

    async def process(
        self, event_id, handler=None, max_attempts: int = 3
    ) -> WebhookEvent:
        async with self._database.session_factory() as session:
            claim = await session.execute(
                update(WebhookEvent)
                .where(
                    WebhookEvent.id == event_id,
                    WebhookEvent.status.in_(
                        [WebhookStatus.received.value, WebhookStatus.retrying.value]
                    ),
                )
                .values(
                    status=WebhookStatus.processing.value,
                    attempt_count=WebhookEvent.attempt_count + 1,
                )
            )
            await session.commit()
            event = await session.get(WebhookEvent, event_id)

            if claim.rowcount != 1:
                return event

            try:
                if handler is not None:
                    await handler(event)

                event.status = WebhookStatus.processed.value
                event.processed_at = self._clock()
            except Exception as error:
                event.status = (
                    WebhookStatus.retrying.value
                    if event.attempt_count < max_attempts
                    else WebhookStatus.failed.value
                )
                event.last_error_code = "webhook.processing_failed"
                event.last_error_message = str(error)

            await session.commit()
            await session.refresh(event)

            return event
