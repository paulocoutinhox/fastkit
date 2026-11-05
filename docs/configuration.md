# Configuration

Every value an environment is lives in its own Python file. Nothing is read from the machine.

```
                 ->  config/stage.py
config/dev.py
                 ->  config/prod.py
```

Stage and production are siblings rather than a chain. Both derive from development, which is what
describes the shape of the application, and neither inherits from the other — otherwise every slack stage
allows itself would reach production by omission, and forgetting one override would be enough. Each states
only what it changes, rebuilt so an override is validated the same way the base was.

## The one variable

The `APP_ENV` variable says **which** configuration to load. Application values belong to that configuration.

```bash
APP_ENV=stage uv run manage.py start
```

The reason is operational: a variable dies with the machine that held it, and a file in the repository comes back with the next deploy. The file says **what** an environment is — which database, which bucket, which captcha provider, how much a password hash costs — and that is the part worth surviving the machine.

## What the product is called

`NAME` in `config/base.py` is the one place the product names itself, and the API title, the sender of every message and the corner of the panel all read it from there.

The `SLUG` constant on the line below is that name reduced to an identifier. It names the site's persistent cookies, its temporary sign-in cookie namespace and the throwaway container used by the schema comparison.

Changing `NAME` therefore rotates the cookie namespace. On an installation that already has readers this signs them out and drops the language and palette they had chosen, which is the same thing a rename means anywhere: the values were kept under a name that no longer exists.

## The values are not in here

This repository is public, so `config/stage.py` and `config/prod.py` declare the shape and never the secret. Every secret published here is a marker — `change-me` in production, `insecure` and `not-for-deployment` in stage, which runs whole under compose with nothing filled in — and whoever deploys fills in their own, in their own private installation. The process refuses to start while production still carries `change-me`.

Two guards keep it that way: every secret a deployed environment declares has to be a placeholder, and nothing published may carry the *shape* of a real credential — an `AKIA`, an `sk_live_`, a `whsec_`, a Sentry DSN, a private key — in any file, not only in `config/`.

## What an environment declares

| Group | What it decides |
| --- | --- |
| `database` | the URL, the pool and whether SQL reaches the log |
| `storage` | filesystem or S3, the bucket, and whether the orphan sweep runs |
| `uploads` | one entry per purpose: the folder, what it accepts, how big it may be, what it is called and what it becomes |
| `security` | the signing key, the encryption keys, how many wrong passwords an account answers, and the cost of a password hash |
| `authentication` | optional email-code and social sign-in, their availability on the site and admin, credentials and short-lived proof lifetimes |
| `email` | which service carries the mail, and the address it sends from — the name a letter carries is the brand's |
| `captcha` | which challenge a public form carries |
| `cache` | whether an assembled public answer is kept and how long it remains valid |
| `site` | the assets, the cookies, the consent asked for, the page size and the tenant a host with no match falls to |
| `languages` | which languages this instance offers, and the name each is called by |
| `retention` | how long a table of records, events, notices or messages keeps a row |
| `sentry` | where a failure is reported, and an environment with no DSN reports nowhere |
| `rate_limit` | the ceiling per IP and in total |
| `trusted_proxies` | which peers may speak for a client, read by the entrypoint and handed to the server |
| `request_max_bytes` | how large a body this process parses into memory may be, which is every body but the multipart one an upload streams, bounded by `upload_max_bytes` instead |
| `readiness_timeout` | how long the readiness probe waits on the database before it answers that this copy cannot serve |
| `cron_*` | whether the worker runs, which queues it serves and how long a claim lasts |

## Optional authentication

The `authentication` group is an `AuthenticationSettings` value. Its email method is disabled and
its social provider dictionary is empty by default. Adding credentials alone does not enable a method.
Set `enabled=True` on each method that should be offered. The `site` and `admin` flags then choose
which surface offers it.

The configuration belongs to the private environment file. This example enables email codes and
Google for both surfaces while keeping every other social provider disabled:

```python
from config.authentication_settings import AuthenticationSettings
from config.dev import settings as dev
from config.email_login_settings import EmailLoginSettings
from config.environment_helper import EnvironmentHelper
from config.social_login_settings import SocialLoginSettings
from enums.social_provider import SocialProvider

settings = EnvironmentHelper.derive(dev, authentication=AuthenticationSettings(email=EmailLoginSettings(enabled=True), social={SocialProvider.GOOGLE: SocialLoginSettings(enabled=True, client_id="your-client-id", client_secret="your-client-secret")}))
```

Keep real credentials in the private installation. Never commit them to this public repository.
The provider secrets use Pydantic's secret type and are never returned by public metadata or account
responses. The public method catalogue contains only availability and provider labels.

### Email code settings

| Field | Default | Contract |
| --- | --- | --- |
| `authentication.email.enabled` | `False` | Enables the method after configuration |
| `authentication.email.site` | `True` | Allows site and site-scoped API sign-in when enabled |
| `authentication.email.admin` | `True` | Allows existing operators to use it on the admin |
| `authentication.email.code_ttl` | `600` | Code validity in seconds, from 60 to 1800 |
| `authentication.email.resend_interval` | `60` | Minimum time between messages to the same scoped address, from 30 to 600 seconds |
| `authentication.email.max_attempts` | `5` | Wrong-code attempt budget, from 1 to 10 |

For a site-only deployment, set `admin=False`. For operator-only email sign-in, set `site=False`.
An admin code never creates an operator. The account must already exist with a permitted panel role.

Configure the `email` service and keep the scheduled mail worker enabled. Console delivery is useful
for development and prints the message locally. SMTP delivery requires the installation's actual mail
configuration. The application queues the code, so delivery capacity and queue health must fit within
its validity period. A suppressed address receives no mail.

A repeated request during the resend interval reuses an unspent challenge and sends no additional
message. A spent, expired or exhausted challenge instead reports how long to wait. After the interval,
a new request replaces the token and code. A code from the older message then opens nothing.

### Social provider settings

Each entry of `authentication.social` is a `SocialLoginSettings` value keyed by `SocialProvider`.
The supported keys are `google`, `apple`, `facebook`, `instagram`, `github`, `linkedin`, `microsoft`
and `discord`. An absent entry is disabled.

| Field | Default | Use |
| --- | --- | --- |
| `enabled` | `False` | Enables this provider |
| `site` | `True` | Offers it on the public site when enabled |
| `admin` | `True` | Offers it on the panel when enabled |
| `client_id` | Empty | The provider application's client ID |
| `client_secret` | Empty | Required by every provider except Apple |
| `team_id` | Empty | The Apple developer team |
| `key_id` | Empty | The Apple signing key ID |
| `private_key` | Empty | The Apple ES256 private key as PEM text |
| `microsoft_tenant` | `consumers` | Personal Microsoft accounts, or one explicit organization tenant UUID |
| `facebook_api_version` | `v26.0` | The Graph API version used by Facebook and Instagram |

Enabled providers require their credentials at startup. Apple requires its team, key ID and a P-256
private key. It also requires `site.scheme="https"` and `site.cookie_secure=True`, because its callback
uses a cross-site form submission. A local plain HTTP configuration cannot enable Apple.

A private Apple configuration can read the downloaded key from a file owned by the deployment:

```python
from pathlib import Path

from config.social_login_settings import SocialLoginSettings

apple = SocialLoginSettings(enabled=True, client_id="your-service-id", team_id="your-team-id", key_id="your-key-id", private_key=Path("/private/credentials/apple-sign-in.p8").read_text())
```

Register the callback as `https://<brand-domain>/account/social/<provider>/callback`, replacing the
provider segment with one of the supported keys. The same callback handles site sign-in, admin sign-in
and authenticated account connections. It is derived from the configured brand domain, rather than
from an arbitrary forwarded host. In multi-tenant mode every participating domain needs an allowed
callback in the provider application. One credential set is configured per provider and installation.

The provider's own application type may limit how many callback domains it permits. In particular,
review the GitHub application type before enabling it across several tenant domains. Provider setup
and these restrictions are detailed in [the account guide](accounts.md#social-provider-setup).

### Authentication state and retention

The `authentication.social_ttl` setting defaults to 600 seconds and accepts 60 to 1800. It bounds the
server-side authorization state and its browser cookie. The `authentication.ticket_ttl` setting
defaults to 60 seconds and accepts 30 to 120. It bounds the browser-bound, single-use ticket used to
hand a completed social sign-in to the admin.

The `retention.authentication_days` setting defaults to one day. Scheduled retention removes expired
email challenges, social attempts and admin tickets in the normal bounded batches. Expiration is
checked when a proof is consumed, independently of when cleanup runs.

The PKCE verifier is encrypted with `security.encryption_keys`. Its column follows the encrypted-field
convention and is included by `uv run manage.py rotate-secrets`. Keep every required decryption key
until stored secrets have been rewritten. The signing key also protects code digests and browser
proofs. All application copies must share the configured keys and database.

The `site.authentication_cookie_prefix` setting names short-lived, host-only sign-in cookies. Each
attempt gets its own cookie so separate tabs do not overwrite one another. Cookies are HTTP-only and
use the configured secure flag. Apple callback cookies use `SameSite=None` and require HTTPS.

## Assembled-answer cache

The cache is [Cachefy](https://github.com/paulocoutinhox/cachefy) over the application database, the same
choice the queue makes for the same reason: every instance reads the same entry and there is nothing new
to operate. `cache.enabled` is off in development, where every request reflects the latest edit, and on in
stage and production. Each thing has a space of its own with a lifetime of its own, because a search and a
privacy policy do not age on the same clock: `cache.search_ttl` is 30 seconds, `cache.home_ttl` and
`cache.banners_ttl` 60, `cache.products_ttl` 120, and `cache.plans_ttl`, `cache.content_ttl` and
`cache.gallery_ttl` 300. The surface belongs to the key rather than the space name, so the API and the site
never read what the other assembled, and clearing one space clears both sides of that one thing.

The library refuses a zero lifetime, so "off" is the environment declining the cache rather than a store
that keeps nothing. It also refuses a value no store could write down, and JSON has a single numeric type,
so a decimal price has no representation there. The cache is transport: a surface dumps through its schema
and reads back through the same one, which restores the exact value. A page therefore holds the same type
whether the cache is on or off.

The cache stores the final data shape used by a page or public API route, not individual query results.
Its key includes every input that can change that shape, including tenant, language, resource address and
product-search term. Admin edits do not evict an entry, and the next answer appears when its TTL expires.

## One brand or many

The `multi_tenant` setting decides, and never a query: registering the first tenant must not change the rules of an
installation in silence. It defaults to off, because a product starts as one brand.

| | one brand | many brands |
| --- | --- | --- |
| the site | looks no host up and answers in the global scope | the host must match `Tenant.domain` |
| the API | asks for no `X-Tenant-Code`, and refuses one that arrives | demands it, always |
| what is written | `tenant_id` null everywhere | the tenant that was resolved |

No table demands a tenant, so an installation serving one brand registers nothing to work. Where there
are many, a tenant row also carries the brand identity — its name, its template folder, its domain, its
contact address, which every tenant has to name. `helpers/brand.py` is what both modes produce, and where there is a single brand those
come from `name`, `site.domain` and `email.from_address` instead.

Development inherits the single brand of the base, because a product starts with one and that is what
somebody develops against. Stage declares many, so that the mode with more to go wrong is exercised
somewhere, and production declares one rather than inheriting it. Aligning the two is the first thing to
do with a fork of this template.

The seed fills the brand the environment serves: with one brand it writes no tenant at all and every row
lands in the scope every reader reaches, and with many it builds the two it always did.

## Who an operator of the panel is answered

An operator whose account belongs to a tenant is answered that tenant and no other, and what they create
is written into it — a payload naming another tenant decides nothing. A row of another brand answers 404,
because it does not exist for them.

The `reaches_shared` flag is a property of the account, granted by an administrator of no brand and off by
default — an operator of a brand never grants it, not even to themselves. It widens the listing and the
lookup to the catalogue rows that belong to no brand, and it governs reading only: writing into a shared row
would let one brand rewrite what another reads, and the panel draws no edit and no delete on one. What
belongs to a person or to the instance itself — accounts, their purchases and subscriptions, the log, the
mail queue and the gateway notices — is never widened.

A catalogue row moved into one brand waits until nothing points at it, because a row of another brand
still pointing at it would point across brands. A row moved into every brand waits until nothing it holds
points into one brand, because a shared plan listing a brand's entitlement would offer it everywhere.

Countries, languages and the list of tenants belong to no brand, so an operator that belongs to one is
refused them.

## Consent

The `site.consent` setting says what a visitor is asked to allow:

| Field | What it decides |
| --- | --- |
| `optional` | the categories this instance asks about, in the order the page draws them. `necessary` is never among them, because nobody is asked about what makes the page exist |
| `version` | which question an answer was given about. Raising it asks everybody again, and a cookie written before it no longer answers |
| `max_age` | how long an answer is kept before it is asked for again |
| `cookie` | the name the answer is written under |

## Replacing the encryption key

The `security.encryption_keys` setting is a list. The first one writes and every one of them reads, which is what
makes a key replaceable: with a single key, changing it turns every stored gateway secret into nothing,
silently, until a webhook fails to authenticate.

```
1. put the new key at the front of the list
2. deploy
3. run `manage.py rotate-secrets`
4. take the old one off the list, and deploy again
```

The rewrite refuses rather than writing over what it could not open. Re-encrypting an unreadable secret
would replace it with nothing, and nobody would know until a gateway called.

Rotation reads only row identifiers and encrypted columns, in pages of 1,000 rows. All replacements
commit together. A credential changed after its read causes `error.secret-changed` and rolls back the
rotation, preserving the newer value. Let that edit finish and run the command again before removing
any decryption key. Unreadable values and cancellation also roll back every replacement.

## Uploads

Every rule about a stored file lives in `settings.uploads`, keyed by purpose, and an environment overrides
whichever ones it wants:

| Field | What it decides |
| --- | --- |
| `folder` | where the key starts, and the only folder a column of that purpose may ever point into |
| `extensions` | what the purpose accepts |
| `max_bytes` | its own ceiling, always bounded by the environment's `upload_max_bytes` |
| `naming` | `uuid` — `<folder>/<date>/<uuid>.<ext>` — or `original` — `<folder>/<date>/<uuid>/<clean-name>.<ext>` |
| `image` | what the bytes become, or `None`, which is what says the purpose is a file and not an image |

Both naming modes put the uuid in the key, which is what the orphan sweep knows a file of ours by and what
keeps two uploads of the same name on the same day from overwriting each other. The readable half is not
what somebody typed: accents are folded, anything that is not a letter or a digit becomes a dash, the whole
thing is cut at 80 characters, and the extension is the one the file was sent with, lower-cased, and only one the rule accepts.

A stored file is served under the type its checked extension names, and never the one the caller claimed.

A file is uploaded by whoever may write a record that keeps one of that purpose — the roles of every service that names it in a file column, or that embeds an image in markup — so an editor uploads a gallery photo and a banner image, and a product file stays the administrator's.

An image rule carries `width`, `height`, `crop`, `image_format`, `quality` and `store`. `store` is the choice
between keeping the bytes exactly as they arrived and keeping the image the rule describes — and either way
the content is decoded first, so an extension can never lie about what the bytes are.

The `image_max_pixels` ceiling is what an image may weigh once decoded, which is a different question from what it weighs
on the wire: a file of a few hundred kilobytes can name a canvas of hundreds of megabytes. Opening a file
reads only its header, so the canvas it names is refused before a single pixel of it is allocated.

## Which service carries the mail

The `email.provider` setting names one, and it is a contract with an implementation per service rather
than a branch inside the queue. Two ship with the template:

| Provider | What it does |
| --- | --- |
| `smtp` | anything a host, a port and a pair of credentials describe — Postmark, SendGrid, Mailgun, Brevo, the SMTP interface of SES, a server of your own |
| `console` | writes the message to the log instead of sending it, which is how a machine with no mail server reads a confirmation link |

Adding one is a class in `helpers/mailer.py` with a `send`, plus a value on `EmailProvider`. Nothing in
the queue, the templates or the suppression list changes, because none of them knows a vendor: the
service hands over a `Letter` — the sender, the recipient, the subject, the HTML and the reply-to — and the provider
decides whether that becomes a MIME envelope on a socket or a JSON body on an HTTP call.

The one thing a provider owes back is the difference between *try again* and *there is nobody there*. It
raises `AddressRefused` for the second, and that is what puts an address on the suppression list and
stops the domain writing to the dead. Everything else is retried.

The map is indexed by the enum, so a value nobody wrote a class for fails the suite rather than quietly
becoming another provider.

## Per tenant

A tenant overrides what it wants and inherits the rest:

```python
tenants = {"acme": TenantSettings(email=ses("no-reply@acme.com"))}
```

A tenant's mailer says which account carries its mail and from which mailbox, and never the name a letter is signed with: that is always the name of the brand the letter was written under, in the header, the footer and the sender alike.

Only the mailer is overridable, and that is deliberate: the tenant of a message is known when it is sent, and the tenant of a file is not known when it is stored — an upload happens before the record that will hold it exists. The storage belongs to the environment.

There is no table of tenant configuration and there should not be one. Changing this is a deploy.

## Where things are written

Everything a running instance writes lives under `data/`:

```
data/app.db      the sqlite database of a developer machine
data/media/      what the filesystem storage keeps
```

One volume covers all of it.
