from datetime import timedelta

import pytest
from sqlalchemy import select

from config.base import EmailSettings, TenantSettings
from enums.email import OutboundEmailStatus
from helpers.dates import now
from helpers.settings import settings
from helpers.templates import ENVIRONMENTS
from services import email as email_module
from services.email import email_service
from services.user import user_service

SMTP = EmailSettings(provider="smtp", host="smtp.acme.com", port=2525, username="robot", password="s3cret", use_tls=False, from_name="Acme", from_address="no-reply@acme.com")


@pytest.fixture
def captured(monkeypatch):
    sent = []

    async def capture(config, message):
        sent.append((config, message))

    monkeypatch.setattr(email_service, "deliver", capture)

    return sent


@pytest.fixture(autouse=True)
def fresh_templates():
    ENVIRONMENTS.clear()

    yield

    ENVIRONMENTS.clear()


async def queued(db, tenant=None, template="password_reset"):
    return await email_service.queue(db, tenant.id if tenant else None, "reader@acme.com", "Olá", template, token="abc", hours=1, link="https://acme.com/account/password-reset/abc")


async def test_a_queued_message_waits_until_the_pass_sends_it(db, monkeypatch, captured):
    monkeypatch.setattr(settings, "email", SMTP)

    record = await queued(db)

    assert record.status == OutboundEmailStatus.PENDING
    assert captured == []

    sent = await email_service.process_pending(db)

    assert [one.id for one in sent] == [record.id]
    assert record.status == OutboundEmailStatus.SENT
    assert record.sent_at is not None


async def test_the_message_is_html_carrying_what_the_context_gave_it(db, monkeypatch, captured):
    monkeypatch.setattr(settings, "email", SMTP)

    await queued(db)
    await email_service.process_pending(db)

    _, message = captured[0]

    assert message["From"] == "Acme <no-reply@acme.com>"
    assert message.get_content_type() == "text/html"
    assert "abc" in message.get_content()


async def test_a_mailer_that_is_down_leaves_the_message_pending(db, monkeypatch):
    monkeypatch.setattr(settings, "email", SMTP)

    async def refuse(config, message):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(email_service, "deliver", refuse)

    record = await queued(db)

    assert await email_service.process_pending(db) == []
    assert record.status == OutboundEmailStatus.PENDING
    assert record.attempts == 1


async def test_a_message_that_keeps_failing_stops_holding_the_queue(db, monkeypatch):
    monkeypatch.setattr(settings, "email", SMTP)

    async def refuse(config, message):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(email_service, "deliver", refuse)

    record = await queued(db)

    for _ in range(email_module.MAX_ATTEMPTS):
        await email_service.process_pending(db)

    assert record.status == OutboundEmailStatus.FAILED
    assert await email_service.process_pending(db) == []


async def test_a_template_nobody_wrote_is_written_down_and_never_raises(db, monkeypatch):
    from models.system_log import SystemLog

    monkeypatch.setattr(settings, "email", SMTP)

    await queued(db, template="nao-existe")

    assert await email_service.process_pending(db) == []

    entry = await db.scalar(select(SystemLog).where(SystemLog.level == "error"))

    assert "TemplateNotFound" in entry.description


async def test_a_tenant_sends_through_its_own_configuration(db, tenant, monkeypatch, captured):
    own = SMTP.model_copy(update={"host": "smtp.own.com", "from_address": "no-reply@own.com"})
    monkeypatch.setattr(settings, "email", SMTP)
    monkeypatch.setattr(settings, "tenants", {tenant.code: TenantSettings(email=own)})

    await queued(db, tenant)
    await email_service.process_pending(db)

    config, message = captured[0]

    assert config.host == "smtp.own.com"
    assert message["From"] == "Acme <no-reply@own.com>"


async def test_a_tenant_without_a_configuration_falls_back_to_the_default(db, tenant, monkeypatch, captured):
    monkeypatch.setattr(settings, "email", SMTP)
    monkeypatch.setattr(settings, "tenants", {tenant.code: TenantSettings()})

    await queued(db, tenant)
    await email_service.process_pending(db)

    assert captured[0][0].host == "smtp.acme.com"


async def test_the_console_provider_writes_instead_of_dialling_out(db, caplog, captured):
    await queued(db)

    with caplog.at_level("INFO"):
        await email_service.process_pending(db)

    assert captured == []
    assert "reader@acme.com" in caplog.text


async def test_the_delivery_hands_the_configuration_to_the_smtp_client(monkeypatch):
    calls = []

    async def fake_send(message, **options):
        calls.append(options)

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    await email_service.deliver(SMTP, email_service.build_message(SMTP, "reader@acme.com", "Olá", "<p>corpo</p>"))

    assert calls[0] == {"hostname": "smtp.acme.com", "port": 2525, "username": "robot", "password": "s3cret", "start_tls": False}


async def test_credentials_left_empty_reach_the_client_as_nothing(monkeypatch):
    calls = []

    async def fake_send(message, **options):
        calls.append(options)

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    anonymous = SMTP.model_copy(update={"username": "", "password": ""})
    await email_service.deliver(anonymous, email_service.build_message(anonymous, "reader@acme.com", "Olá", "<p>corpo</p>"))

    assert calls[0]["username"] is None
    assert calls[0]["password"] is None


async def test_the_file_of_the_tenant_wins_over_the_shared_one(db, tenant, monkeypatch, captured, tmp_path):
    """The tenant folder carries its own colours, and what it does not carry falls back to the shared file."""
    monkeypatch.setattr(settings, "email", SMTP)
    monkeypatch.setattr(settings, "templates_dir", tmp_path)

    partilhado = tmp_path / "global" / "email"
    proprio = tmp_path / "tenants" / tenant.code / "email"
    partilhado.mkdir(parents=True)
    proprio.mkdir(parents=True)

    (partilhado / "password_reset.html").write_text("<p>partilhado {{ token }}</p>")
    (proprio / "password_reset.html").write_text("<p>proprio {{ token }}</p>")

    await queued(db, tenant)
    await email_service.process_pending(db)

    assert "proprio abc" in captured[0][1].get_content()


async def test_what_the_tenant_does_not_carry_comes_from_the_shared_folder(db, tenant, monkeypatch, captured, tmp_path):
    monkeypatch.setattr(settings, "email", SMTP)
    monkeypatch.setattr(settings, "templates_dir", tmp_path)

    partilhado = tmp_path / "global" / "email"
    partilhado.mkdir(parents=True)
    (tmp_path / "tenants" / tenant.code / "email").mkdir(parents=True)

    (partilhado / "password_reset.html").write_text("<p>partilhado {{ token }}</p>")

    await queued(db, tenant)
    await email_service.process_pending(db)

    assert "partilhado abc" in captured[0][1].get_content()


async def test_a_context_that_names_a_reserved_variable_still_renders(db, monkeypatch, captured):
    """The context is a dict and never keywords, so `brand` in it is a value and not a collision."""
    monkeypatch.setattr(settings, "email", SMTP)

    await email_service.queue(db, None, "reader@acme.com", "Olá", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc", brand="colisão")

    assert len(await email_service.process_pending(db)) == 1


async def test_two_nodes_carrying_the_same_tag_dial_a_message_once(db, tenant):
    """The pass is not the claim: without one, two instances of the email tag send the same message twice."""
    record = await email_service.queue(db, tenant.id, "reader@acme.com", "Hello", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    assert await email_service.claim(db, record.id) is True
    assert await email_service.claim(db, record.id) is False


async def test_a_message_a_dead_node_claimed_is_picked_up_again(db, tenant):
    """A row left claimed forever is a message nobody ever sends, which is exactly what the queue exists to avoid."""
    record = await email_service.queue(db, tenant.id, "reader@acme.com", "Hello", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    await email_service.claim(db, record.id)

    record.updated_at = now() - email_module.ABANDONED_AFTER - timedelta(minutes=1)
    await db.commit()

    # The pass itself never sweeps: one write over the whole table belongs where a single node runs it.
    assert await email_service.process_pending(db) == []
    assert await email_service.reclaim_abandoned(db) == 1
    assert [one.id for one in await email_service.process_pending(db)] == [record.id]


async def test_a_message_still_being_sent_is_left_where_it_is(db, tenant):
    """The window is what tells a node that is working from one that is gone, so a claim taken now is nobody else's to take."""
    record = await email_service.queue(db, tenant.id, "reader@acme.com", "Hello", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    await email_service.claim(db, record.id)

    assert await email_service.reclaim_abandoned(db) == 0


async def test_a_message_another_node_took_is_stepped_over(monkeypatch, db, tenant):
    """The row was pending when the pass read it and claimed when it got there, which is what losing the claim looks like."""
    await email_service.queue(db, tenant.id, "reader@acme.com", "Hello", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    async def taken(db_session, record_id):
        return False

    monkeypatch.setattr(email_service, "claim", taken)

    assert await email_service.process_pending(db) == []


async def test_the_queue_is_read_without_the_context_the_message_was_written_from(client, db, tenant, admin_headers):
    """The context of a reset mail carries the token, so a screen that drew it would hand the credential over."""
    await email_service.queue(db, tenant.id, "reader@acme.com", "Reset your password", "password_reset", token="a-live-recovery-token", hours=1, link="https://acme.com/account/password-reset/a-live-recovery-token")

    answer = await client.get("/api/outbound-emails", headers=admin_headers)
    row = answer.json()["items"][0]

    assert row["toAddress"] == "reader@acme.com"
    assert row["status"] == "pending"
    assert "context" not in row
    assert "a-live-recovery-token" not in answer.text


async def test_the_queue_is_filtered_by_what_became_of_a_message(client, db, tenant, admin_headers):
    await email_service.queue(db, tenant.id, "reader@acme.com", "Welcome", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    assert (await client.get("/api/outbound-emails?status=pending", headers=admin_headers)).json()["count"] == 1
    assert (await client.get("/api/outbound-emails?status=sent", headers=admin_headers)).json()["count"] == 0


# What the sender puts in the context of every message, which no caller has to pass.
FRAME = {"t", "language", "brand", "subject"}


def written(name: str) -> set:
    """Every name a template reads, its parent included, minus the ones the sender always provides."""
    from jinja2 import Environment, FileSystemLoader, meta

    environment = Environment(loader=FileSystemLoader("templates/global"))
    wanted, pending = set(), [f"email/{name}.html"]

    while pending:
        parsed = environment.parse(environment.loader.get_source(environment, pending.pop())[0])
        wanted |= meta.find_undeclared_variables(parsed)
        pending += list(meta.find_referenced_templates(parsed))

    return wanted - FRAME


def test_every_message_the_code_queues_carries_what_its_template_reads():
    """The sender builds the path from the name, and a name the template reads and the caller never passes is a hole in what somebody receives."""
    import ast
    import pathlib

    calls = []

    for path in sorted(pathlib.Path(".").rglob("*.py")):
        if any(part in (".venv", "tests", "__pycache__", "node_modules") for part in path.parts):
            continue

        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call) or len(node.args) < 5 or not isinstance(node.args[4], ast.Constant):
                continue

            called = ast.unparse(node.func)

            if called.endswith("email_service.queue") or called.endswith("email_service.to_user"):
                calls.append((f"{path}:{node.lineno}", node.args[4].value, {word.arg for word in node.keywords if word.arg}))

    absent = sorted(f"{where} queues {template} and no template answers it" for where, template, _ in calls if not pathlib.Path(f"templates/global/email/{template}.html").is_file())

    assert len(calls) >= 3, f"the scan found {len(calls)} queued messages, so it is proving nothing"
    assert absent == [], f"these are queued and no template answers them: {absent}"

    holes = sorted(f"{where} queues {template} without {sorted(written(template) - given)}" for where, template, given in calls if written(template) - given)

    assert holes == [], f"these leave a name of their template empty: {holes}"


async def test_the_same_message_to_two_accounts_leaves_in_two_languages(db, tenant):
    """A message is read by whoever receives it, so it is written in the language of that account and not of the request."""
    from tests.factories import make_language

    english = await make_language(db)
    portuguese = await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    reader = await user_service.create(db, {"tenant_id": tenant.id, "email": "reader@acme.com", "password": "s3cret-password", "language_id": english.id})
    leitor = await user_service.create(db, {"tenant_id": tenant.id, "email": "leitor@acme.com", "password": "s3cret-password", "language_id": portuguese.id})

    first = await email_service.to_user(db, tenant.id, reader, "email.password-reset-subject", "password_reset", token="abc", hours=1, link="https://acme.test/x")
    second = await email_service.to_user(db, tenant.id, leitor, "email.password-reset-subject", "password_reset", token="abc", hours=1, link="https://acme.test/x")

    assert (first.locale, second.locale) == ("en", "pt")
    assert first.subject != second.subject


async def test_an_account_that_never_chose_a_language_is_written_to_in_the_one_of_the_request(db, tenant):
    reader = await user_service.create(db, {"tenant_id": tenant.id, "email": "nobody@acme.com", "password": "s3cret-password"})

    assert (await email_service.to_user(db, tenant.id, reader, "email.password-reset-subject", "password_reset", token="abc", hours=1, link="https://acme.test/x")).locale == "en"


async def test_one_message_that_cannot_be_settled_never_takes_the_pass_with_it(db, tenant, monkeypatch):
    """A node that dies halfway through a pass leaves everything it had not reached yet, so the pass survives one message."""
    settings.email.provider = "console"

    first = await queued(db, tenant)
    second = await queued(db, tenant)
    broken = {first.id}

    original = email_service.deliver_record

    async def sometimes(session, record):
        if record.id in broken:
            raise RuntimeError("the mailer refused this one")

        await original(session, record)

    monkeypatch.setattr(email_service, "deliver_record", sometimes)

    sent = await email_service.process_pending(db)

    assert [row.id for row in sent] == [second.id]

    await db.refresh(first)

    assert first.error_code == "RuntimeError"


async def test_a_message_that_was_dialled_and_could_not_be_written_down_is_left_to_the_reclaim(db, tenant, monkeypatch):
    """The send went out and the row never said so, so the claim running out is what hands it back rather than a second send."""
    from sqlalchemy.exc import OperationalError

    settings.email.provider = "console"
    record = await queued(db, tenant)

    async def refused():
        raise OperationalError("UPDATE outbound_email", {}, Exception("the connection went away"))

    monkeypatch.setattr(db, "commit", refused)

    assert await email_service.write_down(db, record.id, None) is None

    monkeypatch.undo()
    await db.refresh(record)

    assert record.status != OutboundEmailStatus.SENT
