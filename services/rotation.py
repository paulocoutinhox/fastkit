from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.db import Base, commit
from helpers.errors import ValidationError
from helpers.security import decrypt, encrypt

# What a column of stored secrets is called, which is the convention the rewrite finds one by.
SUFFIX = "_encrypted"


class RotationService:
    """The rewrite that lets a key be replaced, which reads what is stored with every key and writes it back with the first."""

    def stored(self) -> list[tuple[type, list[str]]]:
        """Every model carrying a secret, read off the schema so one added later is rewritten without anybody remembering."""
        found = []

        for mapper in Base.registry.mappers:
            columns = sorted(column.key for column in mapper.columns if column.key.endswith(SUFFIX))

            if columns:
                found.append((mapper.class_, columns))

        return sorted(found, key=lambda entry: entry[0].__name__)

    async def rewrite(self, db: AsyncSession) -> int:
        rewritten = 0

        for model, columns in self.stored():
            for instance in (await db.execute(select(model))).scalars():
                rewritten += self.rewrite_row(instance, columns)

        await commit(db)

        return rewritten

    def rewrite_row(self, instance, columns: list[str]) -> int:
        rewritten = 0

        for column in columns:
            kept = getattr(instance, column)

            if not kept:
                continue

            opened = decrypt(kept)

            if opened is None:
                raise ValidationError("error.secret-unreadable", column)

            setattr(instance, column, encrypt(opened))
            rewritten += 1

        return rewritten


rotation_service = RotationService()
