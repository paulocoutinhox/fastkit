# Deploy

One image, one process, three surfaces.

## Before the first start

The `config/prod.py` file is published in a public repository, so every secret in it is a marker rather than a
value. Fill them in before you start the image:

| Setting | What it is |
| --- | --- |
| `security.secret_key` | signs every value this server hands out and reads back — the session, the challenge, the cookie answer, the flash |
| `security.encryption_keys` | encrypts the credential of every payment gateway, and the first of the list is the one that writes |
| `database.url` | where the data lives |
| `site.domain` | the address this brand answers at, which is every absolute link the site publishes |
| `storage` | the bucket and its credentials |
| `email` | the smtp host and its credentials |
| `captcha` | the keys of the provider this environment declares |
| `allowed_origins` | the origins a browser may call this from, and nothing else gets in |

**The process refuses to serve while the two security markers are still there**, and it says which one
it found. That refusal exists because a placeholder that works is a placeholder nobody replaces: an
installation that kept it would sign every session and encrypt every gateway credential with a value
anybody can read here.

## The image

```bash
make docker-build
make docker-start APP_ENV=prod
```

The build has three stages: the admin in Node, the site assets in Node, and the API in Python with `uv` installing from a locked file. The two builds are copied into the final image, which runs as a non-root user.

`APP_ENV` is the only variable, and it picks the configuration. Everything else lives in `config/<env>.py`.

## Migrations

There is no Alembic and there should not be one. The schema is `Base.metadata`, and the container applies it before it serves:

```
entrypoint.sh  ->  python manage.py migrate  ->  uvicorn
```

| Command | What it does |
| --- | --- |
| `make migrate` | creates the tables the code declares and leaves the ones that exist untouched |
| `make recreate-schema` | drops everything and builds it again, losing the data |
| `make schema-diff` | compares the configured database with the schema of the code and writes the DDL that is missing |

The `migrate` command creates a **table** that is missing. It does not alter a table that exists, so a new column on a database that already has rows is DDL somebody runs, and `schema-diff` is what writes it.

## The order of a change

| The change | When the DDL runs | Why |
| --- | --- | --- |
| a new column, table or index | **before** the deploy | the old image never names what it does not know, and the new one needs it there |
| a column that goes away | **after** the deploy | the old image still declares it, and the ORM names every mapped column in every select |

Getting that backwards means every read of that table answering `Unknown column` until the deploy lands.

## What one copy needs to reach

| Dependency | Where |
| --- | --- |
| database | MySQL or PostgreSQL in production, SQLite on a developer machine |
| storage | an S3 or R2 bucket in production, `data/media` on disk |
| mail | SMTP in production, the console in development |
| gateway | outbound HTTPS to the provider |

No Redis, no external queue, no separate worker, no system scheduler.

### The bucket

An image is served straight from the bucket, so the address the application answers is the plain address
of the object and nothing of it passes through this process. **What makes an object readable is the
bucket policy**, and the upload never asks for one object at a time: a bucket created today has ACLs
disabled, and a `PUT` that names one is refused with the error AccessControlListNotSupported.

Give the bucket a policy that lets anybody read what is in it:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::your-bucket/*"
        }
    ]
}
```

On AWS that also means turning off *Block all public access* for the bucket, and on R2 it means giving
the bucket a public development URL or a custom domain. Without the policy the uploads still land and
every picture answers 403, which is the one symptom to look for.

## Behind a reverse proxy

The entrypoint tells the server which peers may speak for a client, because a forwarded header is worth
exactly what the connection carrying it is. `--proxy-headers` on its own trusts the loopback and nothing
else, so a proxy running in a container beside the application is not trusted and the scheme and the
client address both stay wrong — every absolute address the application builds says `http`, including the
links it sends by mail, and the per-IP rate limit becomes one bucket shared by everybody.

Set `trusted_proxies` in the configuration of the environment to the address or range the proxy sits in.
`*` is only correct where the application port is not published, because a published port lets anyone
forge the header.

## Running more than one copy

| Piece | How it behaves |
| --- | --- |
| the API | stateless, so any copy answers any request |
| the cron | every copy computes the same slot and one claims it |
| the rate limit | counted in the memory of the process, so the ceiling is per copy |
| the storage | belongs to the environment and is the same for all of them |
| the session | opens at `READ COMMITTED`, which is what lets two copies racing on one row settle it |

## The probes

Two of them, and they answer different questions:

| Probe | What it answers | Who reads it |
| --- | --- | --- |
| `GET /api/meta/health` | that this process is answering, without touching anything | the orchestrator, which restarts what goes quiet |
| `GET /api/meta/ready` | that this copy can serve, by asking the database | the balancer, which stops sending traffic to what refuses |

Liveness never asks the database on purpose: restarting fixes no database, and a database that is down
would restart the whole fleet in a loop. Readiness asks with a deadline — `readiness_timeout` — and
answers **503** when it is not answered, which is what drains one copy instead of making every one of
them fail requests.

Never point either at `/health` — the root belongs to the site, so `/health` answers 200 with a rendered
page even with the database unreachable.
