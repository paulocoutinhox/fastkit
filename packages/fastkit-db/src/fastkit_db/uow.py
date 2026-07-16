import inspect

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Wraps a session with an explicit commit/rollback boundary and after-commit hooks."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self._after_commit: list = []

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()

        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
                await self._run_after_commit()
        finally:
            await self.session.close()
            self.session = None

    def on_after_commit(self, callback) -> None:
        self._after_commit.append(callback)

    async def _run_after_commit(self) -> None:
        try:
            for callback in self._after_commit:
                result = callback()

                if inspect.isawaitable(result):
                    await result
        finally:
            self._after_commit.clear()
