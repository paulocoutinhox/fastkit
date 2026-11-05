from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.conflict_error import ConflictError
from helpers.database_base import Base
from helpers.db import commit
from helpers.security import decrypt, encrypt
from helpers.validation_error import ValidationError

# What a column of stored secrets is called, which is the convention the rewrite finds one by.
SUFFIX = "_encrypted"
BATCH_SIZE = 1000


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

        try:
            for model, columns in self.stored():
                rewritten += await self.rewrite_model(db, model, columns)

            await commit(db)
        except BaseException:
            await db.rollback()

            raise

        return rewritten

    async def rewrite_model(self, db: AsyncSession, model, columns: list[str]) -> int:
        rewritten = 0
        last_id = 0
        table = model.__table__

        while True:
            statement = select(table.c.id, *(table.c[column] for column in columns)).where(table.c.id > last_id).order_by(table.c.id).limit(BATCH_SIZE)
            rows = (await db.execute(statement)).mappings().all()

            if not rows:
                break

            for row in rows:
                changes = self.rewrite_row(row, columns)

                if not changes:
                    continue

                unchanged = [table.c[column] == row[column] for column in columns]
                settled = update(table).where(table.c.id == row["id"], *unchanged).values(**changes)

                if (await db.execute(settled)).rowcount != 1:
                    raise ConflictError("error.secret-changed")

                rewritten += len(changes)

            last_id = rows[-1]["id"]

        return rewritten

    def rewrite_row(self, row, columns: list[str]) -> dict:
        changes = {}

        for column in columns:
            kept = row[column]

            if not kept:
                continue

            opened = decrypt(kept)

            if opened is None:
                raise ValidationError("error.secret-unreadable", column)

            changes[column] = encrypt(opened)

        return changes


rotation_service = RotationService()
