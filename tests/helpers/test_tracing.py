"""A request answers to a name, which is what ties a log line, an audit row and a reported failure together."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from helpers import tracing
from helpers.tracing import HEADER, current_request, named


async def test_an_answer_carries_the_name_of_the_request(client):
    answer = await client.get("/api/meta/health")

    assert len(answer.headers[HEADER]) == 32


async def test_a_name_the_caller_gave_is_the_one_that_answers(client):
    """A gateway or a proxy in front already named the call, and two names for one call tie nothing together."""
    answer = await client.get("/api/meta/health", headers={HEADER: "edge-7f3a91"})

    assert answer.headers[HEADER] == "edge-7f3a91"


@pytest.mark.parametrize("given", ["", "short", "x" * 65, "has spaces", "carriage\r\nreturn", "<script>"])
def test_a_name_this_cannot_carry_is_replaced(given):
    """It reaches a log line as it was written, so anything that could forge one there is not a name."""
    assert named(given) != given
    assert len(named(given)) == 32


async def test_the_name_is_readable_behind_the_route_and_gone_after_it():
    """Nothing behind the route has to be handed it, which is what lets a service write it down without being told."""
    seen = []
    application = FastAPI()
    tracing.setup(application)

    @application.get("/seen")
    async def read_name():
        seen.append(current_request.get())

        return {}

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://acme.test") as reader:
        await reader.get("/seen", headers={HEADER: "edge-abcd1234"})

    assert seen == ["edge-abcd1234"]
    assert current_request.get() == ""
