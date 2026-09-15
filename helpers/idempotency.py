"""A write a client named, where sending it twice opens one payment and answers the same thing both times."""

from datetime import timedelta
from typing import Annotated

from fastapi import Header
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.dates import now
from helpers.db import commit, insert_or_read
from helpers.errors import ConflictError
from models.idempotency import ClientRequest
from models.user import User

HEADER = "Idempotency-Key"

# How long a claim holds the key while the first call is still working, after which one that died stops holding it.
ABANDONED_AFTER = timedelta(minutes=5)

IdempotencyKey = Annotated[str | None, Header(alias=HEADER, max_length=128)]


async def claim(db: AsyncSession, user: User, key: str | None, endpoint: str) -> tuple[ClientRequest | None, dict | None]:
    """The key is taken before the work starts, because two calls that both look first both do the work."""
    if not key:
        return None, None

    read = select(ClientRequest).where(ClientRequest.user_id == user.id, ClientRequest.idempotency_key == key)
    taking = ClientRequest(user_id=user.id, idempotency_key=key, endpoint=endpoint)
    named = await insert_or_read(db, taking, read)
    await commit(db)

    if named is taking:
        return named, None

    if named.endpoint != endpoint:
        raise ConflictError("error.idempotency-key-reused")

    if named.answer is not None:
        return named, named.answer

    if not await take_over(db, named):
        raise ConflictError("error.idempotency-key-in-flight")

    return named, None


async def take_over(db: AsyncSession, named: ClientRequest) -> bool:
    """Takes a key the first call never answered on, and says whether this caller got it: reading the window and then deciding lets every call that read it work."""
    abandoned = update(ClientRequest).where(ClientRequest.id == named.id, ClientRequest.answer.is_(None), ClientRequest.claimed_at < now() - ABANDONED_AFTER).values(claimed_at=now())
    taken = (await db.execute(abandoned)).rowcount == 1

    await db.commit()

    return taken


async def settle(db: AsyncSession, named: ClientRequest | None, answer: dict) -> None:
    if named is None:
        return

    named.answer = answer
    await commit(db)
