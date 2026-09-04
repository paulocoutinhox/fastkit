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

`APP_ENV` is the only thing that comes from the environment, and it says **which** configuration to load, never what any of it is worth.

```bash
APP_ENV=prod uv run uvicorn main:app
```

The reason is operational: a variable dies with the machine that held it, and a file in the repository comes back with the next deploy. The file says **what** an environment is — which database, which bucket, which captcha provider, how much a password hash costs — and that is the part worth surviving the machine.

## The values are not in here

This repository is public, so `config/stage.py` and `config/prod.py` declare the shape and never the secret. Every key published here is a marker — `change-me`, `insecure`, `not-for-deployment` — and whoever deploys fills in their own, in their own private installation.

Two guards keep it that way: every secret a deployed environment declares has to be a placeholder, and nothing published may carry the *shape* of a real credential — an `AKIA`, an `sk_live_`, a `whsec_`, a Sentry DSN, a private key — in any file, not only in `config/`.

## What an environment declares

| Group | What it decides |
| --- | --- |
| `database` | the URL, the pool and whether SQL reaches the log |
| `storage` | filesystem or S3, the bucket, and whether the orphan sweep runs |
| `uploads` | one entry per purpose: the folder, what it accepts, how big it may be, what it is called and what it becomes |
| `security` | the signing key, the encryption keys, how many wrong passwords an account answers, and the cost of a password hash |
| `email` | the mailer, and the name and address it signs with |
| `captcha` | which challenge a public form carries |
| `cache` | whether an assembled public answer is kept and how long it remains valid |
| `site` | the assets, the cookies, the consent asked for, the page size and the tenant a host with no match falls to |
| `languages` | which languages this instance offers, and the name each is called by |
| `retention` | how long a table of records, events, notices or messages keeps a row |
| `sentry` | where a failure is reported, and an environment with no DSN reports nowhere |
| `rate_limit` | the ceiling per IP and in total |
| `trusted_proxies` | which peers may speak for a client, read by the entrypoint and handed to the server |
| `request_max_bytes` | how large a body this process parses into memory may be, which is every body but the multipart one an upload streams |
| `readiness_timeout` | how long the readiness probe waits on the database before it answers that this copy cannot serve |
| `cron_*` | whether the worker runs, which queues it serves and how long a claim lasts |

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
contact address. `helpers/brand.py` is what both modes produce, and where there is a single brand those
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

The `reaches_shared` flag is a property of the account, granted by an administrator and off by default. It widens
the listing and the lookup to the rows that belong to no brand, and it governs reading only: writing into
a shared row would let one brand rewrite what another reads.

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
thing is cut at 80 characters, and the extension comes from the rule.

An image rule carries `width`, `height`, `crop`, `image_format`, `quality` and `store`. `store` is the choice
between keeping the bytes exactly as they arrived and keeping the image the rule describes — and either way
the content is decoded first, so an extension can never lie about what the bytes are.

The `image_max_pixels` ceiling is what an image may weigh once decoded, which is a different question from what it weighs
on the wire: a file of a few hundred kilobytes can name a canvas of hundreds of megabytes. Opening a file
reads only its header, so the canvas it names is refused before a single pixel of it is allocated.

## Per tenant

A tenant overrides what it wants and inherits the rest:

```python
tenants = {"acme": TenantSettings(email=ses("Acme", "no-reply@acme.com"))}
```

Only the mailer is overridable, and that is deliberate: the tenant of a message is known when it is sent, and the tenant of a file is not known when it is stored — an upload happens before the record that will hold it exists. The storage belongs to the environment.

There is no table of tenant configuration and there should not be one. Changing this is a deploy.

## Where things are written

Everything a running instance writes lives under `data/`:

```
data/app.db      the sqlite database of a developer machine
data/media/      what the filesystem storage keeps
```

One volume covers all of it.
