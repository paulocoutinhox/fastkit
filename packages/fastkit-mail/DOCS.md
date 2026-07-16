# fastkit-mail

Asynchronous, template-based email for FastKit with substitutable providers.

## Installation

```bash
pip install fastkit-mail
pip install "fastkit-mail[smtp]"
```

## Providers

- `SmtpEmailProvider` — sends through any SMTP server, including a local
  MailCatcher on `localhost:1025`.
- `MemoryEmailProvider` — collects messages in memory for local dev and tests.

The configured provider is the only one used; a failure is retried on the same
provider, never silently swapped. Providers are pluggable by name:
`mail_providers.register("ses", factory)` (`fastkit_mail.providers`) adds a
backend a project selects via `settings.mail.provider`.

## Templates

An email template is a directory with `subject.txt`, `body.html` and `body.txt`.
`MailTemplateRenderer` resolves a key like `accounts.password_reset` against the
project directories first, then the package defaults, so a same-path file in the
project wins — that is how a project overrides any email template.

## Sending and preview

```python
delivery = await mail_service.send_template(
    "accounts.password_reset",
    to=[user.email],
    context={"user_name": user.display_name, "reset_url": url},
    locale="pt",
)
preview = mail_service.preview("accounts.welcome", {...})
```

`EmailDelivery` records status, provider message id, attempts and errors. Failed
sends move to `retrying` until `max_attempts`, then `failed`.

A `CircuitBreaker` guards the provider call: a raised exception is logged and turned
into a failed attempt instead of crashing the request, and while the circuit is open
sends fail fast without touching a provider that is known to be down.

## Testing

100% branch coverage, including template override precedence, a missing template,
provider success/failure/retry and SMTP send.

```bash
pytest packages/fastkit-mail --cov=fastkit_mail --cov-branch
```
