import pathlib
import re

import pytest

from helpers import db


class SpyEngine:
    """Stands in for the engine so the test can see the pool being dropped."""

    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


@pytest.fixture
def engine(monkeypatch):
    spy = SpyEngine()
    monkeypatch.setattr(db, "async_engine", spy)

    return spy


async def touch():
    return "done"


async def explode():
    raise RuntimeError("the database refused")


def test_a_command_leaves_no_connection_behind_for_the_next_loop(engine):
    """Each asyncio.run is its own event loop, and a connection the pool kept from one that ended cannot be pinged in the next."""
    assert db.run_scoped(touch()) == "done"
    assert engine.disposed == 1


def test_two_commands_in_a_row_each_get_a_clean_pool(engine):
    """The `create-administrator` command builds the schema in one loop and writes the row in the next, which is where this used to break."""
    db.run_scoped(touch())
    db.run_scoped(touch())

    assert engine.disposed == 2


def test_the_pool_is_dropped_even_when_the_command_fails(engine):
    with pytest.raises(RuntimeError):
        db.run_scoped(explode())

    assert engine.disposed == 1


def test_nothing_that_drives_the_shared_session_opens_a_loop_of_its_own():
    """The pool keeps a connection bound to the loop that opened it, and the seed crashed on a server database for exactly this."""
    driving, read = [], 0

    for path in sorted(pathlib.Path().glob("*/*.py")) + [pathlib.Path("manage.py")]:
        if "tests" in path.parts:
            continue

        body = path.read_text()
        read += 1

        if re.search(r"from helpers\.db import [^\n]*\b(AsyncSessionLocal|async_engine)\b", body) and "asyncio.run(" in body:
            driving.append(str(path))

    assert read > 100, f"the guard read {read} modules, so it is proving nothing"
    assert driving == [], f"these drive the shared session and open a loop of their own instead of run_scoped: {driving}"
