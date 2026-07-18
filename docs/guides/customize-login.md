# Customize the login screen

The login form is declarative — pass a `login` config to `build_page_config`. No template edit.

## Email + password (default)

```python
build_page_config(settings.admin, login={
    "identifier": {"label": "login.email", "type": "email", "autocomplete": "username", "default": ""},
    "identifier_type": "email",
})
```

## Username + password

```python
login={"identifier": {"label": "login.username", "type": "text", "autocomplete": "username", "default": ""},
       "identifier_type": "username"}
```

## A method selector (multi-identifier tenant)

```python
login={
  "identifier": {"label": "login.identifier", "type": "text", "autocomplete": "username", "default": ""},
  "identifier_type": "email",
  "identifier_types": [{"value": "email", "label": "Email"},
                       {"value": "phone", "label": "Phone"},
                       {"value": "cpf",   "label": "CPF"}],
}
```

A non-empty `identifier_types` renders a `<select>`; the chosen value is sent as `identifier_type`.

## OAuth buttons

```python
login={
  "password": True,   # False for OAuth-only
  "oauth": [
    {"name": "google", "label": "Continue with Google",
     "url": "/api/auth/oauth/google", "icon": "brand-google"},
    {"name": "github", "label": "Continue with GitHub",
     "url": "/api/auth/oauth/github", "icon": "brand-github"},
  ],
}
```

The framework renders the buttons; **you** implement the callback routes. A minimal callback:

```python
@router.get("/auth/oauth/google/callback")
async def google_callback(code: str, response: Response):
    profile = await exchange_and_fetch_profile(code)
    user = await account_service.find_or_create(profile)
    session = await session_service.create(user.id)
    response.set_cookie(session_cookie, session.token, httponly=True, ...)
    return RedirectResponse(settings.admin.path)
```

You use `account_service` + `session_service` (fastkit-auth) — FastKit never hardcodes a specific OAuth
provider. Add the captcha with [Add a captcha provider](add-captcha-provider.md). See
[Login & captcha](../admin/login-and-captcha.md).
