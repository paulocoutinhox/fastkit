from datetime import datetime, timezone

from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, TimestampMixin, PrimaryKeyMixin
from fastkit_cache.namespaces import hash_key
from fastkit_cache.provider import CacheHealth, CacheStatus


class CacheEntry(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cache_entry"
    __table_args__ = (
        UniqueConstraint("namespace", "key_hash", name="uq_cache_namespace_key"),
    )

    namespace: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def _namespace_of(key: str) -> str:
    parts = key.split(":")

    return parts[4] if len(parts) >= 6 else "default"


class DatabaseCacheProvider:
    """Portable cache backed by a single table with namespace-scoped clearing."""

    def __init__(self, database, clock=None):
        self._database = database
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def _load(self, session, key: str) -> CacheEntry | None:
        entry = (
            await session.execute(
                select(CacheEntry).where(CacheEntry.key_hash == hash_key(key))
            )
        ).scalar_one_or_none()

        if entry is None:
            return None

        if entry.expires_at is not None and _aware(entry.expires_at) <= self._clock():
            await session.delete(entry)
            await session.commit()

            return None

        return entry

    async def get(self, key: str) -> bytes | None:
        async with self._database.session_factory() as session:
            entry = await self._load(session, key)

            return entry.value if entry is not None else None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        expires_at = self._clock() + _seconds(ttl) if ttl is not None else None

        async with self._database.session_factory() as session:
            existing = (
                await session.execute(
                    select(CacheEntry).where(CacheEntry.key_hash == hash_key(key))
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.value = value
                existing.expires_at = expires_at
            else:
                session.add(
                    CacheEntry(
                        namespace=_namespace_of(key),
                        key_hash=hash_key(key),
                        key=key,
                        value=value,
                        expires_at=expires_at,
                    )
                )

            await session.commit()

    async def delete(self, key: str) -> None:
        async with self._database.session_factory() as session:
            await session.execute(
                delete(CacheEntry).where(CacheEntry.key_hash == hash_key(key))
            )
            await session.commit()

    async def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def touch(self, key: str, ttl: int) -> None:
        value = await self.get(key)

        if value is not None:
            await self.set(key, value, ttl)

    async def increment(self, key: str, amount: int = 1) -> int:
        current = await self.get(key)
        value = int(current.decode("utf-8")) if current is not None else 0
        value += amount

        await self.set(key, str(value).encode("utf-8"))

        return value

    async def clear_namespace(self, namespace: str) -> None:
        async with self._database.session_factory() as session:
            await session.execute(
                delete(CacheEntry).where(CacheEntry.namespace == namespace)
            )
            await session.commit()

    async def health(self) -> CacheHealth:
        try:
            async with self._database.session_factory() as session:
                await session.execute(select(CacheEntry.id).limit(1))

            return CacheHealth(CacheStatus.healthy)
        except Exception as error:
            return CacheHealth(CacheStatus.unavailable, detail=str(error))


def _seconds(ttl: int):
    from datetime import timedelta

    return timedelta(seconds=ttl)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value
