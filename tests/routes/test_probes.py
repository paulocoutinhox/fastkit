"""What a balancer and an orchestrator read, where one says restart me and the other says stop sending me traffic."""

import asyncio

import pytest
from sqlalchemy.exc import OperationalError


async def test_liveness_answers_without_asking_anything(client):
    """Restarting a process fixes no database, so the probe that restarts it never asks one."""
    answer = await client.get("/api/meta/health")

    assert answer.status_code == 200
    assert answer.json()["status"] == "ok"


async def test_readiness_answers_when_the_database_does(client):
    answer = await client.get("/api/meta/ready")

    assert answer.status_code == 200
    assert answer.json()["status"] == "ok"


@pytest.mark.parametrize("failure", [OperationalError("SELECT 1", {}, Exception("gone")), asyncio.TimeoutError()])
async def test_readiness_says_this_copy_cannot_serve(client, monkeypatch, failure):
    """A copy that cannot reach the database keeps taking traffic while it says it is fine, and that is what drains a whole fleet."""

    async def refuse(self, *args, **kwargs):
        raise failure

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.execute", refuse)

    answer = await client.get("/api/meta/ready")

    assert answer.status_code == 503
    assert answer.json()["status"] == "unavailable"


async def test_liveness_still_answers_when_the_database_is_gone(client, monkeypatch):
    """The two say different things on purpose, and this is the difference between draining one copy and restarting them all."""

    async def refuse(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("gone"))

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.execute", refuse)

    assert (await client.get("/api/meta/health")).status_code == 200
