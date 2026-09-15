"""The commands that run wherever the application runs, including inside the image before it serves."""

import io
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from commands import schema_diff, seed
from enums.upload import UploadPurpose
from enums.user import UserRole
from helpers.commands import CommandError, call_command
from helpers.dates import now
from helpers.db import AsyncSessionLocal, run_scoped, visible_database
from helpers.settings import settings
from helpers.storage import storage, uuids_in
from models.upload import StoredFile
from models.user import User
from services.user import user_service


def said(name: str, *arguments, **options) -> str:
    written = io.StringIO()
    call_command(name, *arguments, stdout=written, **options)

    return written.getvalue()


def stale_file(root) -> str:
    """A file this application wrote down and nothing ever claimed, which is the only kind the sweep knows about."""
    key = f"images/gallery/2026/07/29/{uuid4()}.webp"
    target = root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"bytes")

    async def written():
        async with AsyncSessionLocal() as session:
            session.add(StoredFile(uuid=uuids_in(key).pop(), key=key, purpose=UploadPurpose.GALLERY_PHOTO, size=5))
            await session.commit()
            await session.execute(update(StoredFile).where(StoredFile.key == key).values(created_at=now() - timedelta(days=3)))
            await session.commit()

    run_scoped(written())

    return key


async def read_user(username: str):
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(User).where(User.username == username))


def test_migrating_says_where(db):
    """The container runs this before it serves, so a table the image expects is there before the first read."""
    assert said("migrate") == f"schema is up to date at {visible_database()}\n"


def test_an_administrator_is_created_outside_every_tenant(db):
    """The admin sign in resolves in the global scope, so an administrator filed under a tenant could never reach it."""
    printed = said("create-administrator", "--username", "boss", "--email", "boss@acme.com", "--password", "s3cret-password")
    user = run_scoped(read_user("boss"))

    assert printed == f"administrator created with id {user.id}\n"
    assert user.role == UserRole.ADMINISTRATOR
    assert user.tenant_id is None


def test_an_administrator_is_never_created_with_a_password_nobody_chose(db):
    """A password written here opens the whole panel, so the seed's one is never assumed outside the seed."""
    with pytest.raises(CommandError):
        said("create-administrator")

    assert run_scoped(read_user("admin")) is None


def test_an_administrator_is_refused_the_password_the_api_would_refuse(db):
    with pytest.raises(CommandError, match="password"):
        said("create-administrator", "--password", "admin")

    assert run_scoped(read_user("admin")) is None


def test_the_administrator_takes_the_seed_name_and_address_unless_told_otherwise(db):
    said("create-administrator", "--password", "s3cret-password")

    assert run_scoped(read_user("admin")).email == "admin@admin.com"


def test_recreating_the_schema_refuses_without_the_confirmation(db):
    with pytest.raises(CommandError, match="would drop every table.*--yes"):
        call_command("recreate-schema")


def test_recreating_the_schema_leaves_an_empty_database_behind(db, member):
    assert said("recreate-schema", "--yes") == f"schema recreated at {visible_database()}\n"

    async def found():
        async with AsyncSessionLocal() as session:
            return await user_service.find_by_login(session, "reader", member.tenant_id)

    assert run_scoped(found()) is None


def test_running_the_delivery_pass_answers_what_it_touched(db):
    assert said("run-delivery") == "reconciled: 0, expired: 0, delivered: 0, retried grants: 0, retried events: 0\n"


def test_rotating_the_secrets_says_how_many_were_written(db):
    """The command is what makes the key before this one able to be taken away."""
    assert said("rotate-secrets") == "0 stored secrets written again with the first key\n"


def test_sweeping_lists_what_it_would_delete(db, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    key = stale_file(tmp_path)

    printed = said("sweep-files")

    assert key in printed
    assert "1 orphan files" in printed
    assert "--yes" in printed
    assert (tmp_path / key).is_file()


def test_sweeping_and_finding_nothing_is_not_a_failure(db, monkeypatch, tmp_path):
    """Listing is what this command was asked to do, and an empty storage is the answer rather than something going wrong."""
    monkeypatch.setattr(storage, "root", tmp_path)

    printed = said("sweep-files")

    assert "0 orphan files" in printed
    assert "--yes" not in printed


def test_sweeping_deletes_once_confirmed(db, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    key = stale_file(tmp_path)

    assert said("sweep-files", "--yes") == "deleted 1 orphan files\n"
    assert not (tmp_path / key).exists()


def test_the_seed_refuses_outside_dev(monkeypatch):
    monkeypatch.setattr(settings, "environment", "prod")

    with pytest.raises(CommandError, match="only runs in dev and this is prod"):
        call_command("seed", "--yes")


def test_the_seed_refuses_without_the_confirmation(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")

    with pytest.raises(CommandError, match="would rebuild.*--yes"):
        call_command("seed")


def test_the_seed_rebuilds_empties_the_storage_and_says_what_it_wrote(monkeypatch):
    """The seed itself is proved by running it, so what the command owes is the order and the report."""
    steps = []

    async def rebuilt():
        steps.append("schema")

    async def emptied():
        steps.append("media")

    async def filled(session):
        steps.append("rows")

        return {"users": 3}

    monkeypatch.setattr(settings, "environment", "dev")
    monkeypatch.setattr(seed, "recreate_schema", rebuilt)
    monkeypatch.setattr(seed, "discard_media", emptied)
    monkeypatch.setattr(seed.seed_service, "run", filled)

    assert said("seed", "--yes") == "users: 3\n"
    assert steps == ["schema", "media", "rows"]


def test_the_schema_diff_refuses_where_there_is_no_server_to_compare(monkeypatch):
    monkeypatch.setattr(schema_diff, "compared", lambda current: None)

    with pytest.raises(CommandError, match="nothing to compare"):
        call_command("schema-diff")


def test_the_schema_diff_writes_what_the_comparison_found(monkeypatch):
    """The comparison itself talks to Docker and to a server, so what the command owes is asking for it and saying the answer."""
    asked = []

    monkeypatch.setattr(schema_diff, "compared", lambda current: current)
    monkeypatch.setattr(schema_diff, "compare", lambda current: asked.append(current) or {"report": ["TABLES: 1 to create, 0 to remove"], "proposed": 1})

    printed = said("schema-diff", "--current", "dump.sql")

    assert asked == ["dump.sql"]
    assert printed.startswith("comparing dump.sql against the schema of the code\nTABLES: 1 to create, 0 to remove\n")
    assert "the proposal covers 1 creation(s)" in printed


def test_a_required_option_is_named_from_code_like_any_other(db):
    call_command("create-administrator", password="s3cret-password", verbosity=0)

    assert run_scoped(read_user("admin")) is not None


def test_the_schema_diff_says_in_one_line_why_it_could_not_compare(monkeypatch):
    """A docker that is missing or stopped is a reason the comparison cannot run, and a traceback is not how a command refuses."""
    import subprocess

    from services import schema_diff as comparison

    def missing(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(schema_diff, "compared", lambda current: current)
    monkeypatch.setattr(schema_diff, "compare", lambda current: comparison.docker("ps"))
    monkeypatch.setattr(subprocess, "run", missing)

    with pytest.raises(CommandError, match="docker is not installed"):
        call_command("schema-diff", "--current", "dump.sql")
