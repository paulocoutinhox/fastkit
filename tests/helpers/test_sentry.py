from uuid import uuid4

import pytest
import sentry_sdk

from config.base import SentrySettings
from helpers import sentry
from helpers.settings import settings


@pytest.fixture(autouse=True)
def disarmed():
    """A test that armed the tracker must not leave it armed, or the process tries to flush on the way out."""
    yield

    sentry_sdk.init(dsn="")


def test_an_environment_with_no_dsn_reports_nowhere(monkeypatch, caplog):
    """Development and the test suite must never reach the tracker, and having no dsn is what keeps them out."""
    calls = []

    monkeypatch.setattr(settings, "sentry", SentrySettings(dsn=""))
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **options: calls.append(options))

    with caplog.at_level("INFO"):
        assert sentry.setup() is False

    assert calls == []

    # Silence would read the same as running code that never knew about the tracker.
    assert "not reporting" in caplog.text


def test_a_dsn_arms_the_tracker_with_the_environment_and_the_release(monkeypatch):
    """An event that does not say which environment and which version produced it is an event nobody can act on."""
    calls = []

    monkeypatch.setattr(settings, "sentry", SentrySettings(dsn="https://key@example.ingest.sentry.io/1", traces_sample_rate=0.25))
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **options: calls.append(options))

    assert sentry.setup() is True

    assert calls[0]["dsn"] == "https://key@example.ingest.sentry.io/1"
    assert calls[0]["environment"] == settings.environment
    assert calls[0]["release"] == settings.version
    assert calls[0]["traces_sample_rate"] == 0.25


def test_development_carries_no_dsn():
    from config.dev import settings as dev

    assert dev.sentry.dsn == ""


def test_nothing_private_travels_with_a_failure(monkeypatch):
    """The tracker is for knowing what broke, and a token or an address in a frame is not part of that."""
    import json

    captured = []

    monkeypatch.setattr(settings, "sentry", SentrySettings(dsn="https://key@example.ingest.sentry.io/1"))
    sentry.setup()
    monkeypatch.setattr(sentry_sdk.get_client().transport, "capture_envelope", captured.append)

    # The secret exists only at runtime, because a literal would travel as the source line it sits on.
    secret = uuid4().hex

    def failing(token):
        held = token  # noqa: F841

        raise RuntimeError("what broke")

    try:
        failing(secret)
    except RuntimeError:
        sentry_sdk.capture_exception()

    sentry_sdk.flush()

    events = [item.payload.json for envelope in captured for item in envelope.items if item.payload.json and "exception" in item.payload.json]
    text = json.dumps(events)

    assert events, "no event was built"
    assert secret not in text
    assert "RuntimeError" in text


def test_a_failure_still_says_where_it_broke(monkeypatch):
    """Dropping the locals must not cost the stack itself, or the report stops being actionable."""
    captured = []

    monkeypatch.setattr(settings, "sentry", SentrySettings(dsn="https://key@example.ingest.sentry.io/1"))
    sentry.setup()
    monkeypatch.setattr(sentry_sdk.get_client().transport, "capture_envelope", captured.append)

    try:
        raise RuntimeError("what broke")
    except RuntimeError:
        sentry_sdk.capture_exception()

    sentry_sdk.flush()

    frame = [item.payload.json for envelope in captured for item in envelope.items if item.payload.json and "exception" in item.payload.json][0]["exception"]["values"][0]["stacktrace"]["frames"][-1]

    assert frame["function"]
    assert frame["lineno"]
    assert "vars" not in frame


def test_production_reports_errors_and_nothing_else():
    """Whoever deploys fills in the dsn, and what the tracker is allowed to carry is decided here and not there."""
    from config.prod import settings as production

    assert production.sentry.traces_sample_rate == 0.0
    assert production.sentry.send_default_pii is False
    assert production.sentry.include_local_variables is False
