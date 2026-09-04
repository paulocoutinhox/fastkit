import ast
import asyncio
import enum
import importlib
import logging
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from config.base import CaptchaSettings, EmailSettings, RateLimitSettings, Settings, TenantSettings
from helpers import cors, lifespan, log, rate_limiter, security, static
from helpers.settings import settings


def middleware_classes(app: FastAPI) -> list:
    return [entry.cls for entry in app.user_middleware]


def test_the_log_level_follows_the_debug_flag(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    log.setup()

    assert logging.getLogger().level == logging.DEBUG

    monkeypatch.setattr(settings, "debug", False)
    log.setup()

    assert logging.getLogger().level == logging.INFO


def test_the_chatty_libraries_stay_out_of_the_log():
    log.setup()

    assert logging.getLogger("aiosqlite").level == logging.WARNING
    assert logging.getLogger("botocore").level == logging.WARNING
    assert logging.getLogger("queuefy").level == logging.INFO


def test_sql_reaches_the_log_only_through_the_echo_flag(monkeypatch):
    monkeypatch.setattr(settings.database, "echo", False)
    log.setup()

    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING

    logging.getLogger("sqlalchemy.engine").setLevel(logging.NOTSET)
    monkeypatch.setattr(settings.database, "echo", True)
    log.setup()

    assert logging.getLogger("sqlalchemy.engine").level == logging.NOTSET


def test_cors_allows_credentials_only_with_explicit_origins(monkeypatch):
    application = FastAPI()

    monkeypatch.setattr(settings, "allowed_origins", ["https://admin.example.org"])
    cors.setup(application)

    assert CORSMiddleware in middleware_classes(application)
    assert application.user_middleware[0].kwargs["allow_credentials"] is True


def test_cors_drops_credentials_behind_a_wildcard(monkeypatch):
    application = FastAPI()

    monkeypatch.setattr(settings, "allowed_origins", ["*"])
    cors.setup(application)

    assert application.user_middleware[0].kwargs["allow_credentials"] is False


def test_the_rate_limiter_stays_out_when_it_is_disabled(monkeypatch):
    application = FastAPI()

    monkeypatch.setattr(settings, "rate_limit", RateLimitSettings(enabled=False))
    rate_limiter.setup(application)

    assert middleware_classes(application) == []


def test_the_rate_limiter_guards_the_total_and_the_source_ip(monkeypatch):
    application = FastAPI()

    monkeypatch.setattr(settings, "rate_limit", RateLimitSettings(enabled=True, ip_limit=2, ip_window=60))
    rate_limiter.setup(application)

    assert middleware_classes(application) == [BaseHTTPMiddleware, BaseHTTPMiddleware]


async def test_the_rate_limiter_refuses_a_caller_over_its_share(monkeypatch):
    application = FastAPI()

    monkeypatch.setattr(settings, "rate_limit", RateLimitSettings(enabled=True, ip_limit=1, ip_window=60, total_limit=1000))
    rate_limiter.setup(application)

    @application.get("/ping")
    async def ping():
        return {"status": "ok"}

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get("/ping")).status_code == 200

        refusal = await client.get("/ping")

        assert refusal.status_code == 429

        # A refusal before the application still answers what the application answers, which is the shape the body cap already refuses in.
        assert refusal.json()["code"] == "error.rate-limited"
        assert refusal.json()["detail"]
        assert refusal.headers["retry-after"]


async def test_the_lifespan_creates_the_schema_and_leaves_the_worker_out_when_cron_is_off(monkeypatch):
    monkeypatch.setattr(settings, "cron_enabled", False)

    started = []
    monkeypatch.setattr(lifespan, "build_worker", lambda: started.append(1))

    async with lifespan.lifespan(FastAPI()):
        pass

    assert started == []


async def test_the_lifespan_runs_a_worker_and_lands_the_flight_before_the_process_goes(monkeypatch):
    """A deploy must never cut a pass in half, so leaving the block stops the worker and waits for it."""
    monkeypatch.setattr(settings, "cron_enabled", True)
    monkeypatch.setattr(settings, "cron_poll_seconds", 0.01)

    async with lifespan.lifespan(FastAPI()):
        polling = [task for task in asyncio.all_tasks() if task.get_coro().__qualname__.startswith("Worker.run")]

        assert len(polling) == 1

    assert polling[0].done()


def test_the_media_folder_is_served_when_storage_is_local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_dist", tmp_path / "missing")

    application = FastAPI()

    static.setup(application)

    assert any(getattr(route, "name", None) == "media" for route in application.routes)
    assert not any(getattr(route, "name", None) == "admin-assets" for route in application.routes)


def build_dists(tmp_path, monkeypatch):
    admin = tmp_path / "admin"
    (admin / "assets").mkdir(parents=True)
    (admin / "index.html").write_text("<div id='admin'></div>")
    (admin / "favicon.svg").write_text("<svg/>")

    assets = tmp_path / "site"
    assets.mkdir(parents=True)
    (assets / "styles.css").write_text("body{}")

    monkeypatch.setattr(settings, "admin_dist", admin)
    monkeypatch.setattr(settings.site, "assets", assets)

    application = FastAPI()
    static.setup(application)

    return application


async def test_the_admin_answers_every_path_below_its_own(tmp_path, monkeypatch):
    application = build_dists(tmp_path, monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get("/admin")).text == "<div id='admin'></div>"
        assert (await client.get("/admin/products/1/edit")).text == "<div id='admin'></div>"
        assert (await client.get("/admin/favicon.svg")).text == "<svg/>"


async def test_the_admin_never_serves_a_file_outside_its_own_build(tmp_path, monkeypatch):
    """The path is joined by hand here, so without resolving it first an encoded `..` would read anything the process can."""
    secret = tmp_path / "secret.txt"
    secret.write_text("the database, the config, whatever is above the build")

    application = build_dists(tmp_path, monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        for attempt in ["/admin/../secret.txt", "/admin/%2e%2e%2fsecret.txt", "/admin/..%2fsecret.txt"]:
            response = await client.get(attempt)

            assert "the database" not in response.text, attempt


async def test_what_the_site_build_wrote_is_served_under_a_path_of_its_own(tmp_path, monkeypatch):
    """The pages are rendered and the files are not, so the build owns one path and never competes with a page."""
    application = build_dists(tmp_path, monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get("/static/styles.css")).text == "body{}"


async def test_an_unknown_api_path_is_an_error_and_never_a_page(client):
    """The site takes every path that is left, and answering HTML with a 200 makes a client read a mistyped route as an empty success."""
    for path in ("/api", "/api/nothing-here", "/api/api/commerce/products"):
        answer = await client.get(path)

        assert answer.status_code == 404
        assert answer.json()["code"] == "error.not-found"


async def test_an_unknown_admin_path_is_an_error_when_the_admin_was_never_built(client):
    """The admin serves its own path only when there is a build, and until then it is not a page of the site either."""
    answer = await client.get("/admin/anything")

    assert answer.status_code == 404
    assert answer.json()["code"] == "error.not-found"


async def test_the_media_is_not_mounted_when_a_bucket_serves_it(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.storage, "provider", "s3")
    monkeypatch.setattr(settings, "admin_dist", tmp_path / "missing")
    monkeypatch.setattr(settings.site, "assets", tmp_path / "missing")

    application = FastAPI()
    static.setup(application)

    assert "media" not in [route.name for route in application.routes]


async def test_nothing_is_mounted_when_neither_was_built(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_dist", tmp_path / "missing")
    monkeypatch.setattr(settings.site, "assets", tmp_path / "missing")

    application = FastAPI()
    static.setup(application)

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 404


def test_no_environment_asks_the_machine_for_anything(monkeypatch):
    """What brings the application up has to outlive the machine that hosted it, so a config file reads no variable."""
    files = sorted(pathlib.Path("config").glob("*.py"))

    assert len(files) >= 4, f"the guard read {len(files)} configuration files, so it is proving nothing"

    for path in files:
        assert "os.environ" not in path.read_text(), path


# What a real credential looks like, so one that is pasted in is caught by its shape and not by somebody noticing.
SHAPES = ("AKIA", "ASIA", "sk_live_", "sk_test_", "rk_live_", "whsec_", "SG.", "ingest.sentry.io", "amazonaws.com/", "-----BEGIN")

PLACEHOLDERS = ("change-me", "insecure", "not-for-deployment", "localhost", "no-reply@", "app:app@")


def published() -> list[pathlib.Path]:
    return sorted(pathlib.Path("config").glob("*.py")) + [pathlib.Path("docker-compose.yml"), pathlib.Path("nginx.conf"), pathlib.Path("README.md")]


def test_nothing_published_carries_something_shaped_like_a_real_credential():
    """This repository is public, so a value that only a deployment may hold never reaches a file in it."""
    offenders = [f"{path}: {shape}" for path in published() for shape in SHAPES if shape in path.read_text()]

    assert offenders == [], f"these look like a real credential: {offenders}"


def test_every_secret_a_deployed_environment_declares_is_a_placeholder():
    """Production states what it needs and never what it is worth, and whoever deploys it fills these in."""
    from config.prod import settings as production
    from config.stage import settings as stage

    for deployed in (stage, production):
        secrets = [deployed.security.secret_key, *deployed.security.encryption_keys, deployed.database.url, deployed.storage.access_key, deployed.storage.secret_key, deployed.email.password, deployed.captcha.secret_key]

        assert [value for value in secrets if value and not any(mark in value for mark in PLACEHOLDERS)] == []


def test_what_a_deployed_environment_gets_by_default_is_what_a_deployed_environment_needs():
    """The base states the deployed value and development states what it relaxes, so an environment written later is safe by omission and never by memory."""
    from config.base import SecuritySettings, SiteSettings
    from config.dev import settings as dev

    site = SiteSettings()
    security = SecuritySettings(secret_key="x", encryption_keys=["x"])

    assert site.scheme == "https"
    assert site.cookie_secure is True
    assert site.domain != dev.site.domain, "the shared default is the domain of a development machine"
    assert any(mark in site.domain for mark in PLACEHOLDERS), "the shared default has to read as unset, and never as a working address"

    # What argon2 recommends, which development lowers on purpose so a suite of this size still finishes.
    assert security.password_memory_cost == 65536
    assert dev.security.password_memory_cost < security.password_memory_cost

    assert dev.site.scheme == "http"
    assert dev.site.cookie_secure is False


def test_an_environment_that_serves_one_brand_states_the_domain_it_answers_on():
    """With one brand nothing looks a host up, so this value is every absolute address the application writes: the sitemap, the json-ld, the return of a checkout and the link inside an email."""
    from config.dev import settings as dev
    from config.prod import settings as production
    from config.stage import settings as stage

    for deployed in (stage, production):
        if deployed.multi_tenant:
            continue

        assert deployed.site.domain != dev.site.domain, f"{deployed.environment} answers on the domain of a development machine"
        assert any(mark in deployed.site.domain for mark in PLACEHOLDERS), f"{deployed.environment} publishes a domain of its own instead of a marker"


def test_the_development_settings_run_on_the_machine_of_whoever_develops():
    from config.dev import settings as dev

    assert dev.environment == "dev"
    assert dev.debug is True
    assert dev.storage.provider == "filesystem"
    assert dev.database.url.startswith("sqlite")
    assert dev.rate_limit.enabled is False


def test_an_environment_with_a_database_server_says_so():
    from config.prod import settings as production
    from config.stage import settings as stage

    for deployed in (stage, production):
        assert deployed.database.url.startswith("mysql")
        assert deployed.rate_limit.enabled is True


def test_only_production_holds_a_bucket_and_an_origin_of_its_own():
    """Stage runs on the machine of whoever runs it, so it carries no key at all — production is the one that reaches out."""
    from config.prod import settings as production
    from config.stage import settings as stage

    assert production.storage.provider == "s3"
    assert production.allowed_origins != ["*"]

    assert stage.storage.provider == "filesystem"
    assert stage.storage.access_key == ""
    assert stage.storage.secret_key == ""


def test_every_environment_survives_a_password_with_punctuation_in_it():
    """An @ or a # inside the password ends the credentials early and turns the rest of it into the host, and the failure only shows up on deploy."""
    from config.prod import settings as production
    from config.stage import settings as stage

    for deployed in (stage, production):
        url = make_url(deployed.database.url)

        assert url.host in ("mysql", "localhost") or "@" not in url.host
        assert url.port == 3306
        assert url.database


def test_a_deployed_environment_keeps_what_development_declared():
    from config.dev import settings as dev
    from config.stage import settings as stage

    assert stage.default_language == dev.default_language
    assert stage.supported_languages == dev.supported_languages
    assert stage.upload_max_bytes == dev.upload_max_bytes


def test_production_is_stricter_than_stage_about_how_much_it_answers():
    from config.prod import settings as production
    from config.stage import settings as stage

    assert production.debug is False
    assert production.rate_limit.ip_limit < stage.rate_limit.ip_limit
    assert production.rate_limit.total_limit < stage.rate_limit.total_limit


def test_a_tenant_that_declares_a_mailer_signs_its_mail_with_its_own_brand():
    """A brand sends under its own name through the same account, which is one entry here and one identity to verify there."""
    from config.base import EmailSettings, TenantSettings, derive
    from config.prod import settings as production

    branded = derive(production, tenants={"acme": TenantSettings(email=EmailSettings(from_name="Acme", from_address="no-reply@acme.com"))})

    assert branded.email_for("acme").from_name == "Acme"
    assert branded.email_for("acme") is not branded.email


def test_a_tenant_production_never_heard_of_sends_through_the_environment():
    """The codes live in the database and a config file names only the ones that override something."""
    from config.prod import settings as production

    assert production.email_for("a-tenant-created-yesterday") is production.email


def test_the_settings_loader_answers_the_environment_module(monkeypatch):
    from helpers import settings as loader

    monkeypatch.setattr(loader, "APP_ENV", "dev")

    assert loader.load().environment == "dev"


@pytest.mark.parametrize("path", ["/api/meta/health", "/api/meta"])
async def test_the_assembled_application_answers(path):
    application = importlib.import_module("main").app

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get(path)).status_code == 200


def test_a_tenant_falls_back_to_the_environment_when_it_declares_nothing():
    assert settings.email_for(None) is settings.email
    assert settings.email_for("ninguem") is settings.email


def test_a_tenant_overrides_the_mailer_and_never_the_bucket():
    """The tenant of a message is known when it is sent, and the tenant of a file is not known when it is stored: an upload happens before the record that holds it exists."""
    assert set(TenantSettings.model_fields) == {"email"}


def test_production_sends_through_ses_and_nothing_else_does():
    from config.dev import settings as dev
    from config.prod import settings as production
    from config.stage import settings as stage

    assert production.email.provider == "smtp"
    assert production.email.host.startswith("email-smtp.")
    assert production.email.use_tls is True

    assert [dev.email.provider, stage.email.provider] == ["console", "console"]


def test_a_tenant_that_declares_a_mailer_of_its_own_never_falls_back():
    from config.base import EmailSettings, TenantSettings, derive
    from config.prod import settings as production

    branded = derive(production, tenants={"acme": TenantSettings(email=EmailSettings(from_name="Acme"))})

    assert branded.email_for("acme") is branded.tenants["acme"].email


def test_only_a_developer_machine_hashes_a_password_cheaply():
    """The cost is what protects a stolen table, and a suite that hashes thousands is the only place it buys nothing."""
    import importlib

    from config.base import SecuritySettings

    recommended = SecuritySettings(secret_key="x", encryption_keys=["y"])

    for name in ("stage", "prod"):
        security = importlib.import_module(f"config.{name}").settings.security

        assert security.password_memory_cost >= recommended.password_memory_cost, name
        assert security.password_time_cost >= recommended.password_time_cost, name
        assert security.password_parallelism >= recommended.password_parallelism, name


class WatchedHasher:
    """Stands in for argon2 and says which thread the work actually ran on."""

    def __init__(self):
        self.threads = []

    def hash(self, raw_password: str) -> str:
        self.threads.append(threading.current_thread())

        return "hashed"

    def verify(self, password_hash: str, raw_password: str) -> bool:
        self.threads.append(threading.current_thread())

        return True


async def test_a_password_is_never_hashed_on_the_loop_that_answers_everything_else(monkeypatch):
    """Argon2 costs tens of milliseconds of cpu on purpose, and spending them here freezes every other request this worker holds."""
    watched = WatchedHasher()
    monkeypatch.setattr(security, "password_hasher", watched)

    await security.hash_password("s3cret-password")
    await security.verify_password("s3cret-password", "hashed")

    assert watched.threads and all(thread is not threading.main_thread() for thread in watched.threads)


def test_the_counter_holds_the_clients_it_saw_last_and_no_more_of_them():
    """An address that stops calling is never hit again, so a plain dict would hold every one that ever called until the process dies."""
    windows = rate_limiter.BoundedWindows(3)

    for number in range(5):
        windows[f"ip-{number}"] = number

    assert list(windows) == ["ip-2", "ip-3", "ip-4"]
    assert len(windows) == 3


def test_a_client_that_is_still_calling_is_never_the_one_dropped():
    windows = rate_limiter.BoundedWindows(3)

    for number in range(3):
        windows[f"ip-{number}"] = number

    assert windows["ip-0"] == 0

    windows["ip-3"] = 3

    assert list(windows) == ["ip-2", "ip-0", "ip-3"]


def test_a_window_that_was_dropped_is_gone_from_the_counter():
    windows = rate_limiter.BoundedWindows(2)
    windows["ip-0"] = 0

    del windows["ip-0"]

    assert list(windows) == []


def test_a_deployed_environment_names_the_proxy_that_stands_in_front_of_it():
    """A deployment runs behind one, and left on the loopback every address it builds says http and every caller counts as one."""
    loopback = importlib.import_module("config.dev").settings.trusted_proxies

    for name in ("stage", "prod"):
        trusted = importlib.import_module(f"config.{name}").settings.trusted_proxies

        assert trusted != loopback, name

        # Trusting everybody is only correct where the port is not published, which is never the shape this repository ships.
        assert "*" not in trusted, name


def test_stage_and_production_are_siblings_and_never_a_chain():
    """Every slack stage gives itself to run without a single secret would otherwise reach production by omission."""
    assert "from config.dev import settings as dev" in pathlib.Path("config/prod.py").read_text()
    assert "config.stage" not in pathlib.Path("config/prod.py").read_text()


def test_the_server_is_told_which_peers_may_speak_for_a_client():
    """A forwarded header is worth what the connection carrying it is, and `--proxy-headers` alone trusts the loopback and nothing else."""
    entrypoint = pathlib.Path("entrypoint.sh").read_text()

    assert "--proxy-headers" in entrypoint
    assert "--forwarded-allow-ips" in entrypoint

    # The value is read out of the configuration the process loads, so it is never written down twice.
    assert "settings.trusted_proxies" in entrypoint


async def test_a_proxy_this_deployment_does_not_name_never_speaks_for_a_client():
    """Behind a proxy nobody trusted, every address this side builds says http and every caller counts as one."""
    forwarded = [(b"x-forwarded-proto", b"https"), (b"x-forwarded-for", b"203.0.113.9")]
    answered = {}

    async def read(scope, receive, send):
        answered["scheme"], answered["client"] = scope["scheme"], scope["client"][0]

    for trusted, scheme, client in ((settings.trusted_proxies, "http", "172.18.0.5"), ("172.18.0.5", "https", "203.0.113.9")):
        await ProxyHeadersMiddleware(read, trusted_hosts=trusted)({"type": "http", "scheme": "http", "client": ("172.18.0.5", 5000), "headers": forwarded}, None, None)

        assert (answered["scheme"], answered["client"]) == (scheme, client)


def test_the_build_reads_both_paths_the_panel_answers_by_from_the_configuration():
    """The panel is served at one and calls the other, and a value it wrote down itself is one that breaks the day the server moves."""
    import re

    source = pathlib.Path("config/base.py").read_text()
    named = set()

    # The site calls the api to count a banner, so it is handed the path by the very same reading and never writes it down either.
    for surface, wanted in (("admin", {"admin_path", "api_path"}), ("site", {"api_path"})):
        reader = pathlib.Path(f"webapps/{surface}/vite.config.js").read_text()
        reading = set(re.findall(r'declaredPath\("(\w+)"\)', reader))

        assert reading == wanted, f"the build of the {surface} stopped reading a path it needs out of the configuration"
        named |= reading

    for name in sorted(named):
        declared = re.search(rf'{name}: str = "([^"]+)"', source)

        assert declared is not None, f"config/base.py no longer declares {name} the way the build reads it"
        assert declared.group(1) == getattr(settings, name)

    assert "__API_PATH__" in pathlib.Path("webapps/admin/src/api/client.js").read_text(), "the panel writes down where the api answers instead of being handed it"

    # Reading the one file that is handed the value proves nothing about the rest of a surface, and a link built by hand slipped through for exactly that reason.
    sources = [(path, number, line.strip()) for folder in ("webapps/admin/src", "webapps/site/src") for path in sorted(pathlib.Path(folder).rglob("*")) if path.suffix in (".js", ".vue") for number, line in enumerate(path.read_text().splitlines(), 1)]
    written = [f"{path}:{number}" for path, number, line in sources if f"{settings.api_path}/" in line and not line.startswith("import ")]

    assert sources, "the guard reads the surfaces it protects, so it proves nothing where it read none"
    assert written == [], f"a surface writes down where the api answers instead of being handed it: {written}"


# What the running application arms and the suite deliberately does not, each with the reason it is left out.
UNARMED = {
    "log": "the suite reads its own output and a second configuration of logging would fight it",
    "sentry": "nothing that runs here is a failure anybody should be told about",
    "rate_limiter": "counting requests would make the order of the tests decide whether one passes",
    "cors": "no browser is involved, so there is no origin to allow",
    "static": "the built assets and the media of a machine are not what any of this proves",
}


def test_the_application_under_test_is_wired_the_way_the_real_one_is():
    """A suite that builds its own application proves nothing about the one that runs, and this is where the two drifted."""
    import pathlib
    import re

    armed = re.compile(r"^\s*(\w+)\.setup\(", re.M)

    def named(source: str) -> set:
        return {match.group(1).removesuffix("_helper") for match in armed.finditer(source)}

    root = named(pathlib.Path("main.py").read_text())
    suite = named(pathlib.Path("tests/conftest.py").read_text())

    assert len(root) >= 6, "the scan read almost nothing out of main.py, so it is proving nothing"
    assert root - suite == set(UNARMED), f"the suite does not arm what the application does, and nobody said why: {sorted(root - suite - set(UNARMED))}"

    wiring = re.compile(r"errors\.setup\([^)]*,[^)]*\)")

    assert wiring.search(pathlib.Path("main.py").read_text()), "main.py stopped handing the error layer the page the site draws"
    assert wiring.search(pathlib.Path("tests/conftest.py").read_text()), "the suite builds an application that answers a bad address differently from the real one"


# Where a table read by an enum key may live, which is everywhere a request or a job is answered.
DISPATCHING = ("config", "helpers", "jobs", "models", "routes", "schemas", "services")

# What answers for part of its enum on purpose, each with the reason it does.
PARTIAL_TABLES = {"OUTCOMES": "the page a buyer lands on has three things to say, and every outcome of a purchase groups into them", "DRAWN_AS": "following the device is drawn by naming no theme at all, so it is the one choice with nothing to name"}


def reached_by(tree: ast.Module) -> dict[int, str]:
    """The name every dict literal of a module is reached by, which is the variable it is bound to or the function that returns it."""
    named = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Dict):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            named[id(node.value)] = getattr(target, "id", "")

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                    named.setdefault(id(inner.value), node.name)

    return named


def dispatch_tables() -> list[tuple[str, str, type, set]]:
    """Every table the code keys entirely by the members of one enum, found in the source instead of named by hand."""
    found = []

    for path in sorted(path for folder in DISPATCHING for path in pathlib.Path(folder).rglob("*.py")):
        module = importlib.import_module(str(path.with_suffix("")).replace("/", "."))
        tree = ast.parse(path.read_text())
        names = reached_by(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict) or not node.keys or id(node) not in names:
                continue

            keys = [key for key in node.keys if isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name)]
            owners = {key.value.id for key in keys}

            if len(keys) != len(node.keys) or len(owners) != 1:
                continue

            named = getattr(module, owners.pop(), None)

            if not isinstance(named, enum.EnumMeta):
                continue

            found.append((f"{path}:{node.lineno}", names[id(node)], named, {getattr(named, key.attr) for key in keys}))

    return found


def test_every_closed_set_the_code_dispatches_on_answers_for_every_value():
    """A table read by a key straight out of an enum turns a value nobody implemented into a 500, wherever it is read."""
    tables = dispatch_tables()
    offenders = [f"{where} ({name}) has nothing for {sorted(str(value) for value in set(enum_class) - answered)}" for where, name, enum_class, answered in tables if name not in PARTIAL_TABLES and set(enum_class) - answered]

    assert len(tables) >= 11, f"the scan found only {len(tables)} of them, so it is proving nothing"
    assert offenders == [], f"a value of the enum has nothing to answer it: {offenders}"


def test_no_table_is_excused_from_answering_for_a_reason_that_is_gone():
    """An excuse outliving what it was written for is one nobody reads again, and it would cover the next table to take that name."""
    excused = {name for _, name, enum_class, answered in dispatch_tables() if name in PARTIAL_TABLES and set(enum_class) - answered}
    stale = sorted(set(PARTIAL_TABLES) - excused)

    assert stale == [], f"these are excused and either no longer exist or already answer for everything: {stale}"


def test_no_route_is_declared_twice_and_none_is_swallowed_by_one_declared_before_it(app):
    """A path answers by the first declaration that matches it, so a literal written after a parameter of the same shape never answers at all."""
    from collections import Counter

    from tests.test_admin_audit import declared

    names = [name for name, _ in declared(app)]
    repeated = sorted(name for name, count in Counter(names).items() if count > 1)

    assert len(names) > 250, f"the guard read only {len(names)} routes, so it is proving nothing"
    assert repeated == [], f"these are declared more than once, and the second never answers: {repeated}"

    swallowed = []

    for index, name in enumerate(names):
        method, path = name.split(" ", 1)

        if "{" in path:
            continue

        segments = path.strip("/").split("/")

        for earlier in names[:index]:
            other_method, other_path = earlier.split(" ", 1)

            if other_method != method or "{" not in other_path:
                continue

            others = other_path.strip("/").split("/")

            if len(others) == len(segments) and all(want.startswith("{") or want == have for want, have in zip(others, segments)):
                swallowed.append(f"{name} never answers, because {earlier} was declared first")

    assert swallowed == [], f"these are swallowed by a parameter declared before them: {swallowed}"


def test_the_proxy_in_front_accepts_the_largest_upload_the_application_does():
    """A body the proxy refuses is a 413 this side never sees, and one it accepts past the ceiling is a limit written twice and honoured once."""
    import pathlib
    import re

    from helpers.settings import settings

    declared = re.search(r"client_max_body_size\s+(\d+)([kmg]?);", pathlib.Path("nginx.conf").read_text(), re.I)

    assert declared is not None, "nginx no longer declares the body it accepts the way this guard reads it"

    scale = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[declared.group(2).lower()]

    assert int(declared.group(1)) * scale == settings.upload_max_bytes, "the proxy and the application disagree on the largest upload"


def test_the_site_and_the_panel_offer_the_same_palettes_in_the_same_order():
    """Two runtimes with no code between them state this twice, and a button that cycles one way here and another there is one nobody can explain."""
    import pathlib
    import re

    from enums.theme import Theme
    from helpers.site import NEXT_THEME

    written = pathlib.Path("webapps/admin/src/stores/theme.js").read_text()
    offered = re.search(r"const THEMES = \[([^\]]+)\]", written)
    cycle = re.search(r"const NEXT = \{([^}]+)\}", written)

    assert offered and cycle, "the panel no longer states its palettes the way this guard reads them"
    assert re.findall(r'"(\w+)"', offered.group(1)) == [theme.value for theme in Theme]
    assert dict(re.findall(r'(\w+): "(\w+)"', cycle.group(1))) == {here.value: there.value for here, there in NEXT_THEME.items()}


def test_the_python_versions_are_the_same_in_every_place_that_names_them():
    """A badge is a claim, and one nothing runs against is a claim that goes stale the day another version is added."""
    import pathlib
    import re
    import tomllib

    badge = re.search(r"badge/python-([\d.%|\s]+)-blue", pathlib.Path("README.md").read_text())
    claimed = sorted(version.strip() for version in badge.group(1).replace("%20", " ").split("|"))

    tested = sorted(re.findall(r'"(\d+\.\d+)"', re.search(r"python-version: \[([^\]]+)\]", pathlib.Path(".github/workflows/test.yml").read_text()).group(1)))
    floor = tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["requires-python"]

    assert claimed == tested, f"the readme claims {claimed} and the suite runs on {tested}"
    assert floor == f">={claimed[0]}", f"the floor is {floor} and the lowest one claimed is {claimed[0]}"
    assert pathlib.Path(".python-version").read_text().strip() == claimed[0], "whoever develops develops on the lowest version the project holds"

    # The image is what runs, so a version named there and nowhere checked is the one free to drift.
    dockerfile = pathlib.Path("Dockerfile").read_text()
    built = re.findall(r"^FROM python:(\d+\.\d+)", dockerfile, re.M)

    assert built == [claimed[0]], f"the image builds on {built} and the lowest version the project holds is {claimed[0]}"

    node_built = sorted(set(re.findall(r"^FROM node:(\d+)", dockerfile, re.M)))
    node_tested = sorted(set(re.findall(r'node-version: "(\d+)"', pathlib.Path(".github/workflows/test.yml").read_text())))

    assert node_built and node_built == node_tested, f"the image builds the front ends on node {node_built} and the pipeline runs them on {node_tested}"


def test_the_colour_of_the_brand_is_stated_in_one_place_and_read_by_both_builds():
    """A colour written twice is two colours the day somebody changes one, and the site and the panel already drew two different blues."""
    import pathlib
    import re

    from helpers.settings import settings

    shared = pathlib.Path("webapps/declared.js").read_text()
    declared = pathlib.Path("config/base.py").read_text()

    # The build reads the configuration by pattern, so what the trap has to prove is that each pattern still finds the value the server holds.
    templated = re.search(r"new RegExp\(`(.+?)`\)", shared)

    assert templated, "the shared reader no longer builds the pattern it looks a path up by"

    crossing = [(pattern.strip("/"), None) for pattern in re.findall(r"stated\((/.+?/), ", shared)]
    crossing += [(templated.group(1).replace("${name}", name), getattr(settings, name)) for name in re.findall(r'declaredPath\("(\w+)"\)', "".join(pathlib.Path(where).read_text() for where in ("webapps/site/vite.config.js", "webapps/admin/vite.config.js")))]

    assert len(crossing) >= 3, f"the scan read only {len(crossing)} values crossing the bridge, so it is proving nothing"

    for pattern, expected in crossing:
        found = re.search(pattern, declared)

        assert found, f"the build looks for {pattern} and config/base.py no longer declares it"

        if expected is not None:
            assert found.group(1) == str(expected), f"the build reads {found.group(1)} where the server holds {expected}"

    for name in ("webapps/site/vite.config.js", "webapps/admin/vite.config.js"):
        config = pathlib.Path(name).read_text()

        assert "brandPlugin" in config, f"{name} no longer writes its palette from the brand"
        assert "config/base.py" not in config, f"{name} reads the configuration on its own instead of through the one reader"

    for name in ("webapps/site/src/style.css", "webapps/admin/src/style.css"):
        css = pathlib.Path(name).read_text()

        assert '@import "./brand.css"' in css, f"{name} does not read the brand the build writes"
        assert not re.search(rf"oklch\([\d.%]+\s+[\d.]+\s+{settings.brand_hue}\b", css), f"{name} writes a colour of the brand by hand"


def test_every_address_the_seed_writes_is_one_the_panel_can_save_back():
    """A seeded row the write schema refuses is a record an operator opens, changes nothing in, and cannot save."""
    from pydantic import ValidationError

    from schemas.tenant import TenantCreate
    from services.seed import ADMIN, MEMBERS, TENANTS

    refused = []

    for entry in TENANTS:
        try:
            TenantCreate(code=entry["code"], name=entry["name"], domain=entry["domain"], email_contact=f"contact@{entry['domain']}", email_administrative=f"admin@{entry['domain']}")
        except ValidationError as error:
            refused.append(f"{entry['domain']}: {error.errors()[0]['loc']}")

    written = [ADMIN["email"]] + [member["email"] for member in MEMBERS]

    for address in written:
        try:
            TenantCreate(code="x", name="X", domain="x.example", email_contact=address)
        except ValidationError as error:
            refused.append(f"{address}: {error.errors()[0]['loc']}")

    assert len(TENANTS) + len(written) >= 5
    assert refused == []


def test_an_environment_that_falls_back_to_a_language_it_does_not_offer_is_refused():
    """Every message is looked up in the default catalog, so a default outside the offered set answers nothing anywhere."""
    import pytest

    from config.base import derive
    from helpers.settings import settings

    with pytest.raises(ValueError, match="every message would be looked up"):
        derive(settings, default_language="de")

    assert derive(settings, default_language="pt", languages={"pt": "Português"}).default_language == "pt"


def test_nobody_is_asked_to_allow_what_the_page_needs_to_exist():
    """The necessary category is the one a visitor is never asked about, and offering it would ask to switch the site off."""
    import pytest

    from config.base import ConsentSettings
    from enums.consent import ConsentCategory

    with pytest.raises(ValueError, match="never one a visitor is asked"):
        ConsentSettings(optional=[ConsentCategory.NECESSARY])

    assert ConsentSettings(optional=[ConsentCategory.ANALYTICS]).optional == [ConsentCategory.ANALYTICS]


async def test_whatever_answers_a_get_answers_a_head(client, site, admin_headers):
    """A crawler, a link checker and an uptime monitor ask with HEAD first, and a resource that refuses it reads as gone."""
    for path in ("/api/meta/health", "/api/meta/ready", "/api/languages/active"):
        assert (await client.head(path)).status_code == 200, path

    for path in ("/", "/plans", "/products", "/robots.txt", "/sitemap.xml"):
        assert (await site.head(path)).status_code == 200, path

    assert (await client.head("/api/users", headers=admin_headers)).status_code == 200


def test_answering_head_never_doubles_what_the_documentation_publishes():
    """A HEAD twin of every route is noise in the contract whoever integrates reads, so the method is answered and never declared."""
    from main import app

    published = app.openapi()["paths"]

    assert sum(1 for methods in published.values() for method in methods if method == "head") == 0
    assert len(published) > 150, "the schema was read as too small to claim anything"


def test_every_file_a_front_end_build_reads_across_the_tree_is_one_its_own_stage_copies():
    """Each front end is built in a stage of its own, so a file copied into the other one is a file this build does not have."""
    import pathlib
    import re

    root = pathlib.Path.cwd()
    stages = {name: body for name, body in re.findall(r"^FROM [^\n]+ AS (\w+)\n(.*?)(?=^FROM |\Z)", pathlib.Path("Dockerfile").read_text(), re.S | re.M)}
    checked = 0

    def reached_from(where: pathlib.Path, target: str) -> pathlib.Path | None:
        found = (where.parent / target).resolve()

        return found.relative_to(root) if found.is_relative_to(root) and not found.is_relative_to(where.parent) else None

    for app in sorted(pathlib.Path("webapps").glob("*/vite.config.js")):
        building = [body for body in stages.values() if f"webapps/{app.parent.name}/package.json" in body]

        assert len(building) == 1, f"no single stage of the image builds {app.parent}"

        copied = {line.split()[1] for line in building[0].splitlines() if line.startswith("COPY ") and not line.startswith("COPY --from")}
        reaching = [(app, target) for target in re.findall(r'from "(\.\./[^"]+)"', app.read_text())]
        reaching += [(style, target) for style in sorted(app.parent.rglob("*.css")) for target in re.findall(r'@source "([^"]+)"', style.read_text())]
        needed = set()

        for where, target in reaching:
            found = reached_from(where, target)

            if found is None:
                continue

            needed.add(str(found))

            # The shared reader reads what the server declares, so the stage needs that file as much as it needs the reader.
            if found.suffix == ".js":
                needed |= {"/".join(named) for named in re.findall(r'"\.\.", "([\w.]+)", "([\w.]+)"', found.read_text())}

        checked += len(needed)
        missing = sorted(path for path in needed if not any(entry.rstrip("/") == path.rstrip("/") for entry in copied))

        assert missing == [], f"the stage building {app.parent} reads these and copies none of them: {missing}"

    assert checked >= 5, f"the scan read only {checked} files across the stages, so it is proving nothing"


def test_every_schema_this_project_builds_is_built_from_the_one_list():
    """The cache was added to what the application creates and not to what the diff compares against, so its table read as one to drop."""
    import ast
    import pathlib

    from helpers.schema import SCHEMAS

    named = []

    for path in sorted(pathlib.Path().glob("*/*.py")):
        if "tests" in path.parts:
            continue

        for node in ast.walk(ast.parse(path.read_text())):
            # Naming one metadata is what lets a second list exist, and the loop over the shared one always reads it through its variable.
            if isinstance(node, ast.Attribute) and node.attr == "create_all" and not isinstance(node.value, ast.Name):
                named.append(f"{path}:{node.lineno} builds {ast.unparse(node.value)}")

    assert named == [], f"these build a schema from a metadata of their own: {named}"

    owned = {table.name for metadata in SCHEMAS for table in metadata.sorted_tables}

    assert len(SCHEMAS) >= 3 and len(owned) > 30, f"the list holds {len(SCHEMAS)} metadata and {len(owned)} tables, so it is proving nothing"
    assert {"cachefy_entry", "queuefy_run"} <= owned, "the queue and the cache each keep their own metadata, and both are tables this application owns"


async def test_no_environment_serves_with_a_secret_this_repository_publishes(monkeypatch):
    """The configuration of a deployment is copied from here, so a secret nobody filled in signs every cookie with a value anybody can read."""
    from fastapi import FastAPI

    from helpers import lifespan as starting
    from helpers.settings import settings

    for name, value in (("secret_key", "change-me-to-a-long-random-string"), ("encryption_keys", ["change-me-to-another-long-random-string"])):
        monkeypatch.setattr(settings.security, name, value)

        with pytest.raises(RuntimeError, match="placeholder this repository publishes"):
            async with starting.lifespan(FastAPI()):
                pass

        monkeypatch.undo()

    # The suite runs on a secret of its own, so the process it arms starts.
    async with starting.lifespan(FastAPI()):
        pass


def test_every_published_environment_still_says_its_secret_was_never_filled_in():
    """The refusal reads a placeholder, so it is worth nothing the day the shipped configuration stops carrying one."""
    import pathlib

    from helpers.lifespan import PLACEHOLDER

    assert PLACEHOLDER in pathlib.Path("config/prod.py").read_text(), "production no longer ships the placeholder the refusal reads"


def test_an_environment_nobody_wrote_lets_no_other_origin_in():
    """A default a published environment has to remember to tighten is the one it forgets, which is the same reason the scheme and the secure cookie were turned around."""
    assert Settings.model_fields["allowed_origins"].get_default(call_default_factory=True) == []


def test_an_environment_nobody_wrote_sends_its_mail_instead_of_printing_it():
    """Printing is what the machine of whoever develops does, and an environment that forgot to configure mail would write every recovery token into its log."""
    assert EmailSettings.model_fields["provider"].get_default() == "smtp"


def test_an_environment_nobody_wrote_still_guards_its_public_forms():
    """Turning the challenge off is a choice an environment writes down, and never what one that said nothing assumes."""
    assert CaptchaSettings.model_fields["provider"].get_default() == "image"
