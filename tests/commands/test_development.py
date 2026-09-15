"""The commands of the machine of whoever develops, each answering for the exact programs it runs."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from helpers.commands import call_command

PYTHON = [sys.executable, "-m"]


def npm(project: str, *arguments: str) -> list[str]:
    return ["npm", "--prefix", f"webapps/{project}", *arguments]


def compose(*arguments: str) -> list[str]:
    return ["docker", "compose", *arguments]


RUNS = {
    "deps": ([], [["uv", "sync"]]),
    "deps-update": ([], [["uv", "lock", "--upgrade"], ["uv", "sync"]]),
    "format": ([], [[*PYTHON, "ruff", "check", "--fix", "."], [*PYTHON, "ruff", "format", "."], npm("admin", "run", "format"), npm("site", "run", "format")]),
    "lint": ([], [[*PYTHON, "ruff", "check", "."], [*PYTHON, "ruff", "format", "--check", "."]]),
    "start": (["--port", "9000"], [[*PYTHON, "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "debug", "--reload"]]),
    "test": (["--coverage", "--", "-k", "money"], [npm("admin", "run", "build"), npm("site", "run", "build"), [*PYTHON, "pytest", "--cov", "--cov-report=html", "--cov-report=term", "-k", "money"]]),
    "admin-deps": ([], [npm("admin", "install")]),
    "admin-start": ([], [npm("admin", "run", "dev")]),
    "admin-build": ([], [npm("admin", "run", "build")]),
    "admin-test": (["--coverage"], [npm("admin", "run", "test:cov")]),
    "admin-format": ([], [npm("admin", "run", "format")]),
    "site-deps": ([], [npm("site", "install")]),
    "site-start": ([], [npm("site", "run", "dev")]),
    "site-build": ([], [npm("site", "run", "build")]),
    "site-test": ([], [npm("site", "run", "build"), npm("site", "run", "test")]),
    "site-format": ([], [npm("site", "run", "format")]),
    "docker-build": ([], [compose("build")]),
    "docker-start": ([], [compose("up", "-d")]),
    "docker-stop": ([], [compose("down")]),
    "docker-restart": ([], [compose("restart")]),
    "docker-start --database": (["--database"], [compose("--profile", "database", "up", "-d")]),
    "docker-stop --database": (["--database"], [compose("--profile", "database", "down")]),
    "docker-restart --database": (["--database"], [compose("--profile", "database", "restart")]),
    "docker-logs": ([], [compose("logs", "-f")]),
    "docker-migrate": ([], [compose("run", "--rm", "--entrypoint", "python", "app", "manage.py", "migrate")]),
    "docker-administrator": (["--username", "boss", "--password", "s3cret-password"], [compose("run", "--rm", "--entrypoint", "python", "app", "manage.py", "create-administrator", "--username", "boss", "--email", "admin@admin.com", "--password", "s3cret-password")]),
}


@pytest.mark.parametrize("name", sorted(RUNS))
def test_a_development_command_runs_exactly_its_programs(monkeypatch, name):
    ran = []
    monkeypatch.setattr(subprocess, "run", lambda arguments, cwd: ran.append(arguments) or SimpleNamespace(returncode=0))

    arguments, expected = RUNS[name]
    call_command(name.split()[0], *arguments)

    assert ran == expected


def test_the_plain_test_runs_hand_pytest_nothing_but_what_was_typed(monkeypatch):
    ran = []
    monkeypatch.setattr(subprocess, "run", lambda arguments, cwd: ran.append(arguments) or SimpleNamespace(returncode=0))

    call_command("test")
    call_command("admin-test")

    assert ran[2] == [*PYTHON, "pytest"]
    assert ran[3] == npm("admin", "run", "test")
