"""A body this process parses into memory has a ceiling, because one request is enough to take a whole node down."""

import io

from helpers.body_limit import BodyLimit
from helpers.i18n import translate
from helpers.settings import settings

BIG = b"x" * (settings.request_max_bytes + 1)


async def test_a_body_past_the_ceiling_is_refused_before_a_route_reads_it(client, tenant_headers):
    answer = await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "application/json"})

    assert answer.status_code == 413
    assert answer.json()["code"] == "error.payload-too-large"


async def test_a_refused_body_leaves_with_what_every_answer_carries_and_in_the_language_asked(client, tenant_headers):
    """The ceiling sits inside what stamps and translates an answer, so its refusal is not the one answer without them."""
    answer = await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "application/json", "accept-language": "pt-BR"})

    assert answer.headers["x-content-type-options"] == "nosniff"
    assert answer.headers["x-request-id"]
    assert answer.json()["detail"] == translate("error.payload-too-large", "pt")


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


async def test_a_disconnect_is_forwarded_without_completing_the_partial_body():
    messages = [{"type": "http.request", "body": b"half", "more_body": True}, {"type": "http.disconnect"}]
    received = []

    async def receive():
        return messages.pop(0)

    async def application(scope, receive, send):
        received.append(await receive())
        received.append(await receive())

    await BodyLimit(application, settings.request_max_bytes)({"type": "http", "path": "/", "headers": [(b"transfer-encoding", b"chunked")]}, receive, None)

    assert received == [{"type": "http.request", "body": b"half", "more_body": True}, {"type": "http.disconnect"}]


async def test_what_is_not_a_request_is_never_measured():
    """A lifespan carries no body, and a middleware that read one would hold the boot of the process."""
    passed = []

    async def application(scope, receive, send):
        passed.append(scope["type"])

    await BodyLimit(application, settings.request_max_bytes)({"type": "lifespan"}, None, None)

    assert passed == ["lifespan"]


async def test_a_length_written_in_digits_that_are_not_ascii_is_no_length_at_all():
    """A superscript two reads as a digit and converts to nothing, and this middleware has no handler above it to catch that."""
    passed = []

    async def application(scope, receive, send):
        passed.append(scope["path"])

    await BodyLimit(application, settings.request_max_bytes)({"type": "http", "path": "/api/signin", "headers": [(b"content-length", "\u00b2".encode("latin-1"))]}, None, None)

    assert passed == ["/api/signin"]


async def test_body_chunks_reach_the_application_before_the_whole_request_arrives():
    messages = [{"type": "http.request", "body": b"first", "more_body": True}, {"type": "http.request", "body": b"last", "more_body": False}]
    received = []

    async def receive():
        return messages.pop(0)

    async def application(scope, receive, send):
        received.append(await receive())

        assert len(messages) == 1

        received.append(await receive())

    await BodyLimit(application, settings.request_max_bytes)({"type": "http", "path": "/", "headers": [(b"transfer-encoding", b"chunked")]}, receive, None)

    assert [message["body"] for message in received] == [b"first", b"last"]


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
    from app import app
    from helpers.body_limit import streaming_paths

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


async def test_an_upload_address_refuses_a_body_past_the_largest_upload_before_anybody_is_asked_who_sent_it(client, monkeypatch):
    """The form is spooled to disk before the guard of the route runs, so an address that takes a file is bounded even for a caller with no account."""
    monkeypatch.setattr(settings, "upload_max_bytes", 1000)

    answer = await client.post("/api/account/avatar", files={"file": ("big.png", b"z" * 2000, "image/png")})

    assert answer.status_code == 413


async def test_upload_limits_follow_nested_router_prefixes():
    from fastapi import APIRouter, FastAPI, UploadFile

    from helpers.body_limit import streaming_paths

    application = FastAPI()
    outer = APIRouter(prefix="/outer")
    inner = APIRouter(prefix="/inner")

    @inner.post("/file")
    async def receive(file: UploadFile):
        return {"name": file.filename}

    outer.include_router(inner)
    application.include_router(outer, prefix="/api")

    assert [pattern.pattern for pattern in streaming_paths(application)] == ["^/api/outer/inner/file$"]


async def test_chunked_uploads_use_the_upload_ceiling(client, admin_headers):
    boundary = "streamed-upload"

    async def chunks():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="book.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()

        for _ in range(settings.request_max_bytes // 65536 + 1):
            yield b"x" * 65536

        yield f"\r\n--{boundary}--\r\n".encode()

    answer = await client.post("/api/uploads/product-file", content=chunks(), headers=admin_headers | {"content-type": f"multipart/form-data; boundary={boundary}"})

    assert answer.status_code == 201
    assert answer.json()["size"] > settings.request_max_bytes


async def test_chunked_uploads_past_the_upload_ceiling_close_the_parser_files(client, monkeypatch):
    import starlette.formparsers

    monkeypatch.setattr(settings, "upload_max_bytes", 1000)
    opened = []
    original = starlette.formparsers.SpooledTemporaryFile

    def tracked(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)

        return handle

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", tracked)
    boundary = "limited-upload"

    async def chunks():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="book.pdf"\r\n\r\n'.encode()
        yield b"x" * 500
        yield b"x" * 1000
        yield f"\r\n--{boundary}--\r\n".encode()

    answer = await client.post("/api/uploads/product-file", content=chunks(), headers={"content-type": f"multipart/form-data; boundary={boundary}"})

    assert answer.status_code == 413
    assert answer.json()["code"] == "error.payload-too-large"
    assert opened
    assert all(handle.closed for handle in opened)


async def test_the_body_ceiling_counts_actual_bytes_even_with_a_smaller_declared_length(client, tenant_headers):
    answer = await client.post("/api/signin", content=BIG, headers=tenant_headers | {"content-type": "application/json", "content-length": "1"})

    assert answer.status_code == 413
    assert answer.json()["code"] == "error.payload-too-large"
