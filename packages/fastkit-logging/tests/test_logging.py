import logging

import pytest_asyncio
from sqlalchemy import select

from fastkit_core.context.request import RequestContext, reset_request_context, set_request_context
from fastkit_logging.config import JsonLogFormatter, build_file_handler, setup_logging
from fastkit_logging.models import SystemLog
from fastkit_logging.sanitize import REDACTED, sanitize
from fastkit_logging.service import AuditLogService, SystemLogService


def test_sanitize_redacts_sensitive_keys():
    payload = {"email": "a@b.c", "password": "secret", "nested": {"access_token": "x", "value": 1}}

    cleaned = sanitize(payload)

    assert cleaned["email"] == "a@b.c"
    assert cleaned["password"] == REDACTED
    assert cleaned["nested"]["access_token"] == REDACTED
    assert cleaned["nested"]["value"] == 1


def test_sanitize_handles_lists_and_scalars():
    assert sanitize([{"token": "x"}, "plain"]) == [{"token": REDACTED}, "plain"]
    assert sanitize(42) == 42


def test_sanitize_covers_high_value_markers():
    cleaned = sanitize({"api_key": "sk-1", "bearer": "b", "cvv": "123", "ssn": "111", "card_number": "4111", "safe": "ok"})

    assert cleaned["api_key"] == REDACTED
    assert cleaned["bearer"] == REDACTED
    assert cleaned["cvv"] == REDACTED
    assert cleaned["ssn"] == REDACTED
    assert cleaned["card_number"] == REDACTED
    assert cleaned["safe"] == "ok"


def test_sanitize_does_not_over_redact_benign_keys():
    cleaned = sanitize({"wildcard": "*.example.com", "discard_reason": "spam", "scorecard": 5})

    assert cleaned["wildcard"] == "*.example.com"
    assert cleaned["discard_reason"] == "spam"
    assert cleaned["scorecard"] == 5


def test_sanitize_depth_guard_does_not_leak_deep_secrets():
    deep = current = {}

    for _ in range(12):
        current["child"] = {}
        current = current["child"]

    current["password"] = "leak"

    assert "leak" not in str(sanitize(deep))


def test_json_formatter_includes_context():
    token = set_request_context(RequestContext(request_id="req-1", tenant_id=7, user_id="u-1"))

    try:
        record = logging.LogRecord("fastkit", logging.INFO, __file__, 1, "hello", None, None)
        line = JsonLogFormatter().format(record)
    finally:
        reset_request_context(token)

    assert '"request_id":"req-1"' in line
    assert '"tenant_id":7' in line


def test_json_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("fastkit", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())

    line = JsonLogFormatter().format(record)

    assert "exception" in line
    assert "boom" in line


def test_build_file_handler_creates_parent(tmp_path):
    handler = build_file_handler(str(tmp_path / "nested" / "app.log"), json_format=True)

    assert (tmp_path / "nested").exists()
    assert isinstance(handler.formatter, JsonLogFormatter)
    handler.close()


def test_build_file_handler_plain(tmp_path):
    handler = build_file_handler(str(tmp_path / "app.log"), json_format=False)

    assert not isinstance(handler.formatter, JsonLogFormatter)
    handler.close()


def test_setup_logging_dev_and_prod(tmp_path):
    dev_root = setup_logging("INFO", str(tmp_path / "dev.log"), "dev")
    assert dev_root.level == logging.INFO
    assert len(dev_root.handlers) == 2

    prod_root = setup_logging("WARNING", str(tmp_path / "prod.log"), "prod")
    assert prod_root.level == logging.WARNING
    assert any(isinstance(handler.formatter, JsonLogFormatter) for handler in prod_root.handlers)


@pytest_asyncio.fixture
async def context_reset():
    token = set_request_context(RequestContext(request_id="req-2", tenant_id=3, user_id="00000000000000000000000000000001"))

    yield

    reset_request_context(token)


async def test_system_log_service_persists(database, context_reset):
    service = SystemLogService(database, "test")

    row = await service.record("INFO", "security", "login", "user logged in", payload={"password": "x", "ok": True})

    assert row is not None

    async with database.session_factory() as session:
        stored = (await session.execute(select(SystemLog))).scalars().all()

    assert len(stored) == 1
    assert stored[0].payload == {"password": REDACTED, "ok": True}
    assert stored[0].request_id == "req-2"


async def test_system_log_service_accepts_lowercase_level(database, context_reset):
    service = SystemLogService(database, "test")

    row = await service.record("warning", "security", "login", "suspicious attempt")

    assert row is not None
    assert row.level == "warning"


async def test_system_log_service_survives_db_failure(context_reset):
    def broken_factory():
        raise RuntimeError("db down")

    service = SystemLogService(broken_factory, "test")

    assert await service.record("ERROR", "database", "down", "connection lost") is None


async def test_audit_log_service_records_before_after(database, context_reset):
    service = AuditLogService(database)

    row = await service.record("update", "User", resource_id="1", before={"name": "a", "token": "x"}, after={"name": "b"})

    assert row.action == "update"
    assert row.before_data == {"name": "a", "token": REDACTED}
    assert row.after_data == {"name": "b"}
    assert row.user_id is not None


async def test_audit_log_service_without_snapshots(database, context_reset):
    service = AuditLogService(database)

    row = await service.record("delete", "User", resource_id="9")

    assert row.before_data is None
    assert row.after_data is None
