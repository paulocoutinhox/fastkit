# Add a captcha provider

A captcha has two halves: a **server provider** (verifies the payload) and, optionally, a **client
adapter** (renders itself + collects the payload).

## 1. The server provider

```python
# app/captcha_hcaptcha.py
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.errors import CAPTCHA_INVALID, CAPTCHA_REQUIRED

class HCaptchaProvider(CaptchaProvider):
    name = "hcaptcha"

    def __init__(self, secret, site_key):
        self._secret = secret
        self._site_key = site_key

    @property
    def enabled(self):
        return True

    async def verify(self, payload):
        token = (payload or {}).get("token")
        if not token:
            raise AuthenticationError(CAPTCHA_REQUIRED, message="captcha token required")
        if not await verify_with_hcaptcha(self._secret, token):
            raise AuthenticationError(CAPTCHA_INVALID, message="captcha failed")

    def client_config(self):
        return {"provider": "hcaptcha", "enabled": True, "site_key": self._site_key,
                "script_url": "https://js.hcaptcha.com/1/api.js"}
```

Register it at import time and select it in settings:

```python
from fastkit_auth.captcha.providers import captcha_providers
captcha_providers.register("hcaptcha", lambda settings: HCaptchaProvider(
    settings.auth.captcha.secret_key, settings.auth.captcha.site_key))
```

```toml
[auth.captcha]
provider = "hcaptcha"
```

A provider that needs its own routes (a self-hosted challenge/image) overrides `mount_routes(router)` —
see the built-in `ImageCaptchaProvider`.

## 2. The client adapter

If your provider isn't token-via-a-global-script, register a client adapter from `_extra_js.html`:

```html
<script>
FastKit.captcha.register("hcaptcha", {
  mount: function ($container, config) {
    // render the widget into $container
    return { collect: function () { return Promise.resolve({ token: hcaptcha.getResponse() }); } };
  }
});
</script>
```

`config` is your `client_config()`. `initLogin` mounts the adapter into `#login-captcha` and sends the
`collect()` payload with the login. See [Login & captcha](../admin/login-and-captcha.md).
