# Architecture

One process, three surfaces and one database. Nothing else runs beside it: no broker, no worker process, no scheduler daemon.

## The flow of a request

```
routes/  ->  schemas/  ->  services/  ->  models/
   |            |             |              |
 HTTP        validation    business        table
             and shape      rules
```

Every request walks the same way, and no layer skips the next.

| Layer | What it does | What it never does |
| --- | --- | --- |
| `routes/` | receives, delegates, answers a schema | hold a business rule |
| `schemas/` | validates and renames between camelCase and snake_case | touch the database |
| `services/` | the rules | know about HTTP, raise `HTTPException`, read a header |
| `models/` | columns, indexes and relationships | carry behaviour |

## The folders

| Folder | What it holds |
| --- | --- |
| `config/` | one file per environment, stage and production both deriving from development |
| `enums/` | the closed sets of the domain |
| `helpers/` | what every module shares: database, auth, storage, i18n, captcha, site |
| `jobs/` | the scheduled work, declared on the queue |
| `locale/` | `en.json`, `pt.json` and `es.json`, the words the API and the site answer with |
| `models/` | the tables |
| `routes/` | the HTTP surface, with `routes/site/` rendering pages instead of JSON |
| `schemas/` | the Pydantic shapes in and out |
| `services/` | the rules |
| `templates/` | the Jinja templates of the site and of every email |
| `webapps/` | the two front-end packages, each with its own npm |

## One file per domain

A domain appears with the same file name in every layer it needs:

```
enums/commerce.py   models/commerce.py   schemas/commerce.py   services/commerce.py   routes/commerce.py
```

A file holding ten classes of one domain is right. A file holding classes of two domains is not.

## Two surfaces over one table

The admin edits records and the site and the apps consume content, so they read the same table through different schemas:

| Reader | Schema | What it carries |
| --- | --- | --- |
| admin | `ProductSchema` | the raw columns, with `image` as a storage key |
| client | `CatalogProductSchema` | `imageUrl` already resolved, plus `owned` |

A client never receives a storage key. It receives an address.

Every resource a client reads carries a random UUID. The autoincrementing key stays what relationships and
admin routes are built on, and the UUID is the name a client is allowed to keep and hand back — counting a
banner view is one, and a sequential id there would say how many of them exist.

## The assembled-answer cache

What is kept is the assembled answer — the map or the list after storage keys, relations and the language
asked for have already become what a page or an endpoint serves. A hit therefore skips all the work that
built it, rather than replaying a handful of cached query results.

Development leaves the cache off. Stage and production keep entries in the application database through
[Cachefy](https://github.com/paulocoutinhox/cachefy), shared by every process, and a store that cannot be
reached is a miss rather than an error. Keys include the surface, tenant, language and every address or search term that changes the
answer. Nothing evicts on an admin write: expiry is the only invalidation rule, and the retention job removes
expired rows.

## The CRUD factory

Most of what a resource needs comes from declaring attributes on a service:

```python
class ProductService(CrudService):
    model = Product
    search_fields = ("slug",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "entitlement_id", "featured", "active")
    ordering_fields = ("id", "name", "slug", "price", "position", "created_at")
    default_ordering = "position"
    relations = ("tenant", "credits_currency")
    label_fields = ("name",)
    file_fields = {"image": UploadPurpose.PRODUCT_IMAGE, "file": UploadPurpose.PRODUCT_FILE}
    position_field = "position"
```

The `helpers/crud.py` factory turns that into a list, a lookup, a read, three writes and a reorder route.

The `file_fields` declaration maps a column to the purpose it belongs to rather than listing names, which is what says
where a key stored in that column may point. A key naming another purpose is refused.

What is deleted is not that list but what the row **stops mentioning**, and a row mentions a file in
three ways: a key in a column of its own, a link inside markup the panel authors — declared as
`markup_fields` — and the free-form `meta`. Saving a record claims what it mentions and releases what it
mentioned before and no longer does, so a picture taken out of a page goes with the edit. What nothing
ever claimed is left to the orphan sweep.

The `roles` declaration is what says who reaches the resource, and the factory guards every route the declaration
builds with it. It defaults to the administrator, so changing who reaches a whole resource is one line
on the service and never a route at a time.

A deletion the database refuses answers what actually happened. A unique key refused on a write is a
duplicate, and a foreign key refused on a deletion is a row something still points at, so the two carry
different codes:

| What the database refused | What the answer says |
| --- | --- |
| a unique key, on a write | `error.duplicated-record` |
| a foreign key, on a deletion | `error.record-still-referenced` |

## A resource written once per language

`LocalizedService` holds the rule for a resource that exists once per language: the language asked for
wins, English answers for what it does not have, a tenant's own row outranks the shared one, and a
listing answers exactly one row per key. What the key is comes from `localized_key`.

| Base | Its key | Who uses it |
| --- | --- | --- |
| `TaggedService` | `tag` | content and galleries, reached by an address carrying the tag |
| `PlanService` | `code` | the plan, which is the same subscription sold once per market |

## One contract, one implementation per vendor

Five things here are written the same way, because all five are the same shape: a captcha, a postal code
lookup, a payment gateway, a storage and the service that carries the mail. Each is a base class with the
methods a caller needs, a class per vendor, and a `PROVIDERS` map keyed by an enum.

Two rules make that worth having. The first is **when a mistake is caught**: the base is an `ABC` with
abstract methods, and the map builds its providers on import, so a vendor class that implements nothing
fails as the process starts rather than inside somebody's request. The payment gateway is the exception
and uses `__init_subclass__` instead, because its rules are conditional — a gateway that declares itself
queryable owes one more method, and an `ABC` cannot say that.

The second is that **a provider is reached by an index and never by falling through**. `PROVIDERS[enum]`,
not a chain of `if`s ending in one branch that takes whatever nobody classified — that last branch is a
new vendor silently becoming another one. A value added to the enum with no class behind it fails the
suite, which is exactly when you want to hear about it.

Adding a vendor is therefore a class and an enum value. Nothing that calls it changes, and nothing else
has to learn that it exists.

## Talking to somebody else

Every call that leaves this machine carries a deadline. The failure that matters is not a server that is
down — that one refuses at once — but a server that accepts the connection and then says nothing: without
a deadline the caller waits for whatever the client library happened to pick, which is a number nobody
here decided. The captcha and the postal code get five seconds because a form is waiting on them, the
gateway and the reconciliation ten, the checkout fifteen because opening a session is the slowest thing a
vendor does, and the mail server fifteen as the only one that does not speak HTTP.

A guard finds the modules that reach another machine — whatever imports `httpx` or `aiosmtplib` — and
fails when a client is opened or a message is sent without one, rather than naming the calls it knows
about.

Every call this side makes to another machine reads its body through one function, `helpers.remote.body_of`,
which answers a map or nothing at all. A bare `.json()` raises on a body that is not JSON, so a gateway
answering 200 with a maintenance page would become a 500 of ours rather than a refusal of theirs.

What an unreadable body then means belongs to the caller: a refusal for the captcha, nothing found for a
postal code, an empty account for a query to a gateway, and a checkout that was never opened.

## A body this process reads whole

Reading a whole body into memory is how one request takes a node down rather than many, and the rate
limiter counts requests. `helpers/payload.py` is a middleware, mounted outermost, that refuses a body past
`request_max_bytes` with a 413 — by its declared length where it has one, and by counting the bytes as they
arrive where it does not.

A multipart body is not measured there — but only at an address that actually takes a file, which is read
off the application by looking for an `UploadFile` in the signature of every route. The content type is
what the caller chose to send, so it never decides whether a body is measured: a sign-in wearing
`multipart/form-data` would otherwise be exempt and read whole into memory.

An upload never sits in memory: it streams to a spooled file and answers to the ceiling of its purpose.

## A number a caller typed

A number larger than a column holds is not refused by the database: it overflows inside the driver and
becomes a 500. The ceiling of each column width is declared once, beside the identifier type, and every
place a number comes in reads one of them — the identifier in the path, a filter on the query string, the
`offset` of any listing, the page number of a listing of the site, and every integer a write carries in
its body.

The body is the one that hurts most, because SQLite holds whatever it is handed: a `position` past what a
32-bit column keeps passes the whole suite here and answers out of range on MySQL, in production, on a
screen nobody tested again. So the bound is the width of the column and never a number somebody picked,
and a trap compiles every table in the MySQL dialect to check each field against the column it lands in.

## What costs cpu does not run on the loop

An async process has one loop, and whatever holds it holds everybody's request. What matters is not the
total work but how long the loop stands still: while it computes, the health probe, the page and the API
read all wait behind it.

| What | What it cost, measured | Where it is now |
| --- | --- | --- |
| the argon2 of a sign in | 35 ms of cpu, and an unrelated request waited up to 37 ms | a thread, where the same wait is 0.13 ms |
| reading the zone database | 15.6 ms, on every `/api/meta` call and every timezone a schema validated | a constant read once, at 0.0014 ms |

Measuring hashing throughput is the wrong question and answers a 25% gain. The hash does not need to be
faster — everything else needs to keep running. `prepare` became async along with it, which lines the
hook set up: `validate`, `after_save` and `before_delete` already were, and it was the odd one out.

## A listing reads its rows once

A listing reads everything it draws in one query and never one query per row. The photos of the galleries
a tenant offers are read for all of them at once and grouped, on the site and on the API alike — the same
defect fixed on one side and left on the other is worse than not fixing it, because whoever reads the
fixed side believes the rule holds everywhere.

## Which peers may speak for a client

A forwarded header is worth exactly what the connection carrying it is. `--proxy-headers` on its own
trusts the loopback and nothing else, so behind a reverse proxy in a container beside it, nothing is
trusted and two things break quietly: every absolute address this side builds says `http` on an `https`
site — the sitemap, the robots file, the Stripe return urls and the newsletter link that leaves by mail
— and the per-IP rate limit collapses into one shared bucket, where a single caller spends everybody's
budget.

The `trusted_proxies` setting lives where configuration lives, and the entrypoint reads it from the very
configuration the process loads. Trusting `*` is only ever correct where the application port is not
published, because a published port lets anyone forge the header and the limit stops existing.

## What one call is called

The `helpers/tracing.py` module reads the `X-Request-Id` a caller or a proxy already set, or mints one, keeps it in
a context variable and returns it on the answer. Every log line carries it, and every audit row written
in the panel keeps it beside what was done — which is how a webhook, a delivery and an email that came
from one call are read together instead of hunted for.

A name this cannot carry is replaced rather than passed on, because it reaches a log line as it was
written.

## Who changed what

The CRUD factory writes to `system_log`, in the `admin` category, who created, edited, deleted and
reordered which records. It is one place for all 31 resources, because the factory is one place.

Nothing from the body reaches the record: a payload carries passwords and gateway secrets, and an audit
trail is read by more people than the form was.
