# Add a mail provider

Register a factory in the `mail_providers` registry at import time, then select it in settings.

```python
# app/providers.py
from fastkit_mail.providers import mail_providers

class SendgridProvider:
    def __init__(self, api_key):
        self._api_key = api_key

    async def send(self, message):
        # message carries to/subject/html/text/headers
        await post_to_sendgrid(self._api_key, message)

def build_sendgrid(settings, context):
    return SendgridProvider(settings.mail.sendgrid_api_key)

mail_providers.register("sendgrid", build_sendgrid)
```

Select it:

```toml
[mail]
provider = "sendgrid"
```

The mail service renders templates, records a delivery, and calls your provider's `send` under a retry
policy. For tests, register a recording provider (fastkit-testkit ships fakes) and assert on captured
messages. See [mail package](../packages/mail.md) and [Providers](../concepts/providers.md).
