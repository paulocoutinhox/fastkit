from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update

import manage
from enums.upload import UploadPurpose
from enums.user import UserRole
from helpers.dates import now
from helpers.db import AsyncSessionLocal, run_scoped
from helpers.storage import storage, uuids_in
from models.upload import StoredFile
from services.user import user_service


async def test_an_administrator_is_created_outside_every_tenant(db):
    """The admin sign in resolves in the global scope, so an administrator filed under a tenant could never reach it."""
    user_id = await manage.create_administrator("root", "root@acme.com", "s3cret-password")
    user = await user_service.get(db, user_id)

    assert user.role == UserRole.ADMINISTRATOR
    assert user.tenant_id is None


async def test_running_the_delivery_pass_answers_what_it_touched(db):
    assert await manage.deliver_once() == {"reconciled": 0, "expired": 0, "delivered": 0, "retried_grants": 0, "retried_events": 0}


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


def test_the_parser_and_the_dispatch_name_the_very_same_commands():
    """One declared in the parser and forgotten in the map is a KeyError somebody meets at a terminal, and no test named it."""
    parser = manage.build_parser()
    declared = {choice for action in parser._subparsers._group_actions for choice in action.choices}

    assert len(declared) > 5, "the guard read too few commands to claim anything"
    assert declared == set(manage.commands(None)), f"the parser and the dispatch disagree: {declared ^ set(manage.commands(None))}"


def test_the_parser_declares_every_command():
    parser = manage.build_parser()

    assert parser.parse_args(["migrate"]).command == "migrate"
    assert parser.parse_args(["run-delivery"]).command == "run-delivery"
    assert parser.parse_args(["sweep-files"]).yes is False
    assert parser.parse_args(["seed"]).yes is False

    arguments = parser.parse_args(["create-administrator", "--username", "root", "--email", "root@acme.com", "--password", "s3cret-password"])

    assert arguments.username == "root"


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        manage.build_parser().parse_args([])


def test_recreate_schema_refuses_without_the_confirmation(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["manage.py", "recreate-schema"])

    assert manage.main() == 1

    printed = capsys.readouterr().out

    assert "would drop every table" in printed
    assert "--yes" in printed


async def test_recreate_schema_leaves_an_empty_database_behind(db, member):
    assert await user_service.find_by_login(db, "reader", member.tenant_id) is not None

    await manage.recreate_schema()

    async with AsyncSessionLocal() as session:
        assert await user_service.find_by_login(session, "reader", member.tenant_id) is None


def test_recreate_schema_from_the_command_line(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["manage.py", "recreate-schema", "--yes"])

    assert manage.main() == 0
    assert "schema recreated" in capsys.readouterr().out


def test_the_database_it_names_hides_the_password(monkeypatch):
    monkeypatch.setattr(manage.settings.database, "url", "mysql+aiomysql://app:s3cret@db:3306/account")

    visible = manage.visible_database()

    assert "s3cret" not in visible
    assert visible == "mysql+aiomysql://app:***@db:3306/account"


def test_the_database_it_names_is_shown_whole_when_it_holds_no_password(monkeypatch):
    monkeypatch.setattr(manage.settings.database, "url", "sqlite+aiosqlite:///./app.db")

    assert manage.visible_database() == "sqlite+aiosqlite:///./app.db"


def test_migrating_from_the_command_line(monkeypatch, capsys):
    """The container runs this before it serves, so a table the image expects is there before the first read."""
    monkeypatch.setattr("sys.argv", ["manage.py", "migrate"])

    manage.main()

    assert "schema is up to date" in capsys.readouterr().out


def test_create_administrator_from_the_command_line(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["manage.py", "create-administrator", "--username", "boss", "--email", "boss@acme.com", "--password", "s3cret-password"])

    manage.main()

    assert "administrator created" in capsys.readouterr().out


def test_run_delivery_from_the_command_line(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["manage.py", "run-delivery"])

    manage.main()

    assert "delivered: 0" in capsys.readouterr().out


def test_sweep_files_lists_what_it_would_delete(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    monkeypatch.setattr("sys.argv", ["manage.py", "sweep-files"])

    key = stale_file(tmp_path)

    assert manage.main() == 0

    printed = capsys.readouterr().out

    assert key in printed
    assert "1 orphan files" in printed
    assert "--yes" in printed
    assert (tmp_path / key).is_file()


def test_sweep_files_finding_nothing_is_not_a_failure(monkeypatch, capsys, tmp_path):
    """Listing is what this command was asked to do, and an empty storage is the answer rather than something going wrong."""
    monkeypatch.setattr(storage, "root", tmp_path)
    monkeypatch.setattr("sys.argv", ["manage.py", "sweep-files"])

    assert manage.main() == 0

    printed = capsys.readouterr().out

    assert "0 orphan files" in printed
    assert "--yes" not in printed


def test_sweep_files_deletes_once_confirmed(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    monkeypatch.setattr("sys.argv", ["manage.py", "sweep-files", "--yes"])

    key = stale_file(tmp_path)

    assert manage.main() == 0
    assert "deleted 1 orphan files" in capsys.readouterr().out
    assert not (tmp_path / key).exists()


def test_create_administrator_defaults_to_the_seed_account():
    arguments = manage.build_parser().parse_args(["create-administrator"])

    assert (arguments.username, arguments.email, arguments.password) == ("admin", "admin@admin.com", "admin")


def test_seed_refuses_outside_dev(monkeypatch, capsys):
    monkeypatch.setattr(manage.settings, "environment", "prod")
    monkeypatch.setattr("sys.argv", ["manage.py", "seed", "--yes"])

    assert manage.main() == 1
    assert "only runs in dev" in capsys.readouterr().out


def test_schema_diff_from_the_command_line(monkeypatch):
    """The comparison itself talks to Docker and to a server, so what the command owes is calling it."""
    called = []

    monkeypatch.setattr("sys.argv", ["manage.py", "schema-diff"])
    monkeypatch.setattr(manage, "run_schema_diff", lambda current: called.append(current) or 0)

    assert manage.main() == 0
    assert called == [None]


def test_rotate_secrets_from_the_command_line(monkeypatch, capsys):
    """The command is what makes the key before this one able to be taken away."""
    monkeypatch.setattr("sys.argv", ["manage.py", "rotate-secrets"])

    assert manage.main() == 0
    assert "stored secrets written again with the first key" in capsys.readouterr().out
