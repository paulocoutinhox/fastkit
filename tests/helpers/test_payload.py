"""A body this process parses into memory has a ceiling, because one request is enough to take a whole node down."""

import io

from helpers.payload import BodyLimit
from helpers.settings import settings

BIG = b"x" * (settings.request_max_bytes + 1)


async def test_a_body_past_the_ceiling_is_refused_before_a_route_reads_it(client, tenant_headers):
    answer = await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "application/json"})

    assert answer.status_code == 413
    assert answer.json()["code"] == "error.payload-too-large"


async def test_the_webhook_is_refused_the_same_way(client):
    """It is the one address a stranger reaches without a session, and it reads the raw body to check a signature."""
    answer = await client.post("/api/webhooks/whatever", content=BIG)

    assert answer.status_code == 413


async def test_a_body_that_never_says_how_long_it_is_counted_as_it_arrives(client, tenant_headers):
    """A chunked request declares no length, so the ceiling is only known while the bytes are being read."""

    async def chunks():
        for _ in range(3):
            yield b"y" * settings.request_max_bytes

    answer = await client.post("/api/signin", content=chunks(), headers=tenant_headers | {"content-type": "application/json"})

    assert answer.status_code == 413


async def test_a_body_inside_the_ceiling_reaches_the_route(client, tenant_headers):
    answer = await client.post("/api/signin", json={"login": "nobody@acme.com", "password": "wrong"}, headers=tenant_headers)

    assert answer.status_code != 413


async def test_an_upload_is_not_measured_here_because_it_never_sits_in_memory(client, admin_headers):
    """A multipart body streams to disk and is capped by the rule of its purpose, so this ceiling is not the one it answers to."""
    body = io.BytesIO(b"z" * (settings.request_max_bytes + 1))
    answer = await client.post("/api/uploads/product-file", files={"file": ("big.pdf", body, "application/pdf")}, headers=admin_headers)

    assert answer.status_code != 413


async def test_a_chunked_body_inside_the_ceiling_reaches_the_route_whole(client, tenant_headers):
    """What was counted is handed on, so a route reads the body it would have read without any of this."""

    async def chunks():
        yield b'{"login": "nobody@acme.com",'
        yield b' "password": "wrong"}'

    answer = await client.post("/api/signin", content=chunks(), headers=tenant_headers | {"content-type": "application/json"})

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.invalid-credentials"


async def test_a_body_that_stops_arriving_is_read_as_what_arrived():
    """A client that hangs up mid body leaves the count where it was, and nothing waits on the rest of it."""
    limit = BodyLimit(None, settings.request_max_bytes)
    messages = [{"type": "http.request", "body": b"half", "more_body": True}, {"type": "http.disconnect"}]

    async def receive():
        return messages.pop(0)

    assert await limit.taken(receive) == (b"half", True)


async def test_what_is_not_a_request_is_never_measured():
    """A lifespan carries no body, and a middleware that read one would hold the boot of the process."""
    passed = []

    async def application(scope, receive, send):
        passed.append(scope["type"])

    await BodyLimit(application, settings.request_max_bytes)({"type": "lifespan"}, None, None)

    assert passed == ["lifespan"]


async def test_what_was_counted_is_handed_over_once_and_the_rest_comes_from_where_it_did():
    """An application that reads past the body is asking whether the client is still there, and that answer is not ours to invent."""
    limit = BodyLimit(None, settings.request_max_bytes)
    after = {"type": "http.disconnect"}

    async def receive():
        return after

    replay = limit.replayed(b"counted", receive)

    assert await replay() == {"type": "http.request", "body": b"counted", "more_body": False}
    assert await replay() is after


async def test_a_body_wearing_the_content_type_of_an_upload_is_still_measured(client, tenant_headers):
    """The header is what the caller chose to send, so it never decides whether a route reads a body whole."""
    answer = await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "multipart/form-data; boundary=x"})

    assert answer.status_code == 413
    assert answer.json()["code"] == "error.payload-too-large"


async def test_the_route_never_reads_what_the_ceiling_refused(client, tenant_headers, monkeypatch):
    """It answered before, and only after having read every byte into memory, which is the whole of what this stops."""
    import starlette.requests

    read = []
    original = starlette.requests.Request.body

    async def counted(self):
        body = await original(self)
        read.append(len(body))

        return body

    monkeypatch.setattr(starlette.requests.Request, "body", counted)

    await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "multipart/form-data; boundary=x"})

    assert read == []


async def test_an_address_that_takes_a_file_is_the_one_left_alone():
    """It is read off the application, so an upload written later is streamed without anybody remembering."""
    from helpers.payload import streaming_paths
    from main import app

    assert sorted(pattern.pattern for pattern in streaming_paths(app)) == ["^/account/avatar$", "^/api/account/avatar$", "^/api/uploads/(?P<purpose>[^/]+)$"]


def test_a_route_the_ceiling_exempts_carries_a_ceiling_of_its_own():
    """The exemption is read off the signature, so a route written later takes it without asking: what it must not take is no limit at all."""
    import inspect

    from fastapi import UploadFile

    from helpers import router

    exempt = []
    loose = []

    for group in list(router.ROUTERS) + list(router.SITE_ROUTERS):
        for route in group.routes:
            endpoint = getattr(route, "endpoint", None)

            if endpoint is None or not any(parameter.annotation is UploadFile for parameter in inspect.signature(endpoint).parameters.values()):
                continue

            exempt.append(route.path)
            reached = inspect.getsource(endpoint)

            # Whatever it does with the file, the rule of the purpose is what says how large that file may be.
            if "upload_service" not in reached and "settle_avatar" not in reached:
                loose.append(route.path)

    assert exempt, "the guard found no exempt route, so it is proving nothing"
    assert loose == [], f"these take a file past the body ceiling and enforce none of their own: {loose}"
