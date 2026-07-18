# Login and captcha

Both the login **form** and the **captcha** are fully pluggable — a consumer configures either without
editing a template.

## The declarative login form

`build_page_config(login=…)` produces `config.login`, rendered by `login_card.html`:

```python
build_page_config(
    settings.admin,
    login={
        "identifier": {"label": "login.email", "type": "email",
                        "autocomplete": "username", "default": ""},
        "identifier_type": "email",
        "identifier_types": [],   # non-empty → a <select> to pick the method
        "password": True,          # False → OAuth-only, no password field
        "oauth": [                 # buttons linking to consumer-owned callback URLs
            {"name": "google", "label": "Continue with Google",
             "url": "/api/auth/oauth/google", "icon": "brand-google"},
        ],
    },
)
```

So one deployment logs in by email+password, another by username, another with a method **selector**,
another with Google + N OAuth providers — **no template edit**. `initLogin` sends the selected
`identifier_type` (from the selector or `config.client.login.identifierType`).

### OAuth is a contract, not a hardcoded provider

The framework renders the OAuth buttons; **you** implement the callback routes (verify the OAuth token,
find/create the user, create a session with `session_service`, set the cookie). FastKit provides the
primitives (`account_service`, `session_service`), never a fixed Google/GitHub integration.

## The pluggable captcha

`AuthService.login(..., captcha=payload)` calls the active provider's `verify(payload)`. Built-ins,
selected by `settings.auth.captcha.provider`:

- **`disabled`** — no captcha.
- **`recaptcha`** — reCAPTCHA v3 (token). `client_config()` exposes `site_key`/`action`/`script_url`;
  the script loads only when the provider is `recaptcha`.
- **`image`** — a minimal self-hosted alphanumeric image captcha (Pillow). It mounts
  `GET /auth/captcha/new` (id + PNG data URI) and verifies `{challenge_id, answer}`.

### The client side

`FastKit.captcha` is an adapter registry with built-in `recaptcha` (executes `grecaptcha` for a token)
and `image` (fetches the challenge, renders the `<img>` + answer input + refresh) adapters. `initLogin`
mounts the adapter into `#login-captcha` and `collect()`s the payload on submit — so any captcha works
with **no login-template change**. Register a client adapter for a custom captcha via
`FastKit.captcha.register(name, {mount})` from `_extra_js.html`.

Switch the demo's captcha with `FASTKIT__AUTH__CAPTCHA__PROVIDER=image|recaptcha`. See
[Add a captcha provider](../guides/add-captcha-provider.md) and
[Customize the login screen](../guides/customize-login.md).
