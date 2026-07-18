# fastkit-auth

Sessions, Argon2 passwords, JWT, rate limiting, and a **pluggable captcha**.

## Login

```python
auth = context.component("auth_service")
result = await auth.login(identifier_type="email", identifier_value="a@b.com",
                          password="…", requested_tenant_id=0, captcha=payload)
```

`login` validates the identifier type against the registered set, normalizes it, enforces the
captcha, and matches within the tenant (see [Accounts](accounts.md)).

## Login hardening (do not regress)

- The rate-limit bucket is keyed on the **normalized** identifier, so casing/whitespace variants share
  a bucket.
- A throwaway `dummy_verify` runs whenever no real argon2 verify ran (unknown identifier *or* a
  passwordless account), so timing matches a password account — no user-enumeration oracle.
- A successful login **transparently rehashes** the stored password when the argon2 parameters
  changed.
- An unknown `identifier_type` returns `INVALID_CREDENTIALS`, not a `KeyError` 500.
- Passwords are capped at `auth.password_max_length` (argon2 never hashes an unbounded payload).
- Failure counting is **atomic** (`SET failed_login_count = failed_login_count + 1`), and the lockout
  is set with a conditional `UPDATE … WHERE failed_login_count >= max` — parallel guesses can't slip
  past the lockout.

## Captcha (pluggable)

The `captcha/` subpackage is a full provider system — see
[Login & captcha](../admin/login-and-captcha.md) and
[Add a captcha provider](../guides/add-captcha-provider.md). Built-ins: `disabled`, `recaptcha`
(v3/token), `image` (self-hosted alphanumeric). Selected by `settings.auth.captcha.provider`.

## Known follow-up

The in-memory `RateLimiter` and the captcha providers' in-memory token/challenge stores are
per-process and reset on restart — a shared store is needed for multi-worker. Documented, not
half-wired.
