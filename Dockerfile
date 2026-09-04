FROM node:24 AS admin

WORKDIR /build/webapps/admin

COPY webapps/admin/package.json webapps/admin/package-lock.json ./
RUN npm ci

# Both builds read what the server declares through the one reader, so the tree they read it across is the tree of the repository.
COPY config/base.py /build/config/base.py
COPY webapps/declared.js /build/webapps/declared.js
COPY webapps/admin/ ./
RUN npm run build

FROM node:24 AS site

WORKDIR /build/webapps/site

COPY webapps/site/package.json webapps/site/package-lock.json ./
RUN npm ci

# The classes of the site live in the jinja templates of the backend, so the css build reads them from there.
COPY templates/ /build/templates/
COPY config/base.py /build/config/base.py
COPY webapps/declared.js /build/webapps/declared.js
COPY webapps/site/ ./
RUN npm run build

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

# Which configuration the process loads, and never what any of it is worth.
ENV APP_ENV=prod
ENV PORT=8000

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# The dependencies are their own layer, so a change to the code never reinstalls them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# The site and the admin are served by the same process, both already built.
COPY --from=admin /build/webapps/admin/dist ./webapps/admin/dist
COPY --from=site /build/webapps/site/dist ./webapps/site/dist

# What the instance writes lives in one place, so a volume covers all of it.
RUN mkdir -p /app/data && adduser --disabled-password --gecos "" --uid 12345 fastkit && chown -R fastkit /app
USER fastkit

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
