# fastkit-mail

Async email with templates, resilient providers, and persisted deliveries.

## Send

```python
mail = context.component("mail_service")
await mail.send(to="a@b.com", template="welcome", context={"name": "Ada"}, locale="pt")
```

The service renders the template, records a delivery, and sends through the configured provider.
Transient failures retry under a [retry policy](../concepts/resilience.md).

## Providers

Selected by settings, with a provider registry (`mail_providers`) so you can add your own (SMTP, an
API provider, a fake for tests) — see [Add a mail provider](../guides/add-mail-provider.md) and
[Providers](../concepts/providers.md).

## Deliveries

Each send is persisted as a delivery record, so you have an auditable history and can retry or inspect
failures.

## Known follow-up

Mail counts a breaker-open attempt (documented, to be refined). External IO degrades gracefully rather
than crashing the request.
