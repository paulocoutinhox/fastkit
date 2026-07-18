from fastkit_auth.sessions import hash_token


def test_hash_token_is_deterministic():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")


async def test_create_and_validate(session_service):
    record, raw = await session_service.create(
        1, 0, 5, ip_address="1.1.1.1", user_agent="pytest"
    )

    validated = await session_service.validate(raw)

    assert validated is not None
    assert validated.id == record.id
    assert validated.last_seen_at is not None


async def test_validate_unknown_token(session_service):
    assert await session_service.validate("nope") is None


async def test_validate_expired_session(session_service, clock):
    _, raw = await session_service.create(1, 0, 0)

    clock.advance(200)

    assert await session_service.validate(raw) is None
    assert await session_service.validate(raw) is None


async def test_validate_revoked_session(session_service):
    _, raw = await session_service.create(1, 0, 0)

    assert await session_service.revoke(raw) is True
    assert await session_service.validate(raw) is None


async def test_revoke_unknown_token(session_service):
    assert await session_service.revoke("nope") is False
