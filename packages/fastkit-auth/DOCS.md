# fastkit-auth

Authentication for FastKit: Argon2id passwords, opaque server-side sessions,
signed JWT access tokens, brute-force protection, rate limiting and Google
reCAPTCHA v3.

## Installation

```bash
pip install fastkit-auth
pip install "fastkit-auth[recaptcha]"
```

## Passwords

`PasswordHashService` uses Argon2id, enforces a minimum-length policy, verifies
without leaking timing and reports when a hash needs rehashing.

## Tokens and sessions

`TokenService` issues and verifies HS256 JWTs carrying the subject, session id and
identity/effective tenant. `SessionService` stores only a SHA-256 hash of an
opaque token and supports create, validate (with expiry and last-seen), revoke.

## Login flow

`AuthService.login` runs, in order: rate limit → reCAPTCHA → candidate resolution
(local and global, without revealing which exists) → password verification →
status and lockout checks → session creation → JWT issuance.

- Wrong credentials return a single generic error.
- Repeated failures increment a counter and lock the account for a window.
- An identifier that matches both a local and a global account requires explicit
  resolution (`authentication.ambiguous_identity`).
- A global user adopts the requested tenant as its effective tenant.

## reCAPTCHA v3

`RecaptchaVerifier` validates `success`, `action`, `hostname` and `score`, rejects
reused tokens, and treats a provider outage as a failure rather than an implicit
pass. Error codes: `recaptcha.missing`, `recaptcha.invalid`,
`recaptcha.low_score`, `recaptcha.action_mismatch`, `recaptcha.hostname_mismatch`,
`recaptcha.provider_unavailable`.

## Testing

100% branch coverage, including brute-force, rate limit, ambiguous identity and
every reCAPTCHA and token failure mode.

```bash
pytest packages/fastkit-auth --cov=fastkit_auth --cov-branch
```
