# fastkit-webhooks

Inbound webhook inbox for FastKit with signature verification, idempotency and
retries.

## Installation

```bash
pip install fastkit-webhooks
```

## Providers

A provider verifies a raw request and normalizes it. `HmacWebhookProvider`
verifies an HMAC-SHA256 signature header over the raw body and extracts the
external event id, account and type.

## Flow

```python
event, created = await webhook_service.receive("stripe", headers, raw_body)
await webhook_service.process(event.id, handler)
```

- The signature is verified before anything else; an invalid or missing signature
  is stored as `rejected` and never processed.
- Valid events are stored in the inbox and are unique per
  `(provider, provider_account_id, external_event_id)`, so replays are
  idempotent (`created=False`).
- Processing records attempts; a failing handler moves to `retrying` until
  `max_attempts`, then `failed`.

## Testing

100% branch coverage, including forged and missing signatures, replay
idempotency and retry exhaustion.

```bash
pytest packages/fastkit-webhooks --cov=fastkit_webhooks --cov-branch
```
