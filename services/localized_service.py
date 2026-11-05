from sqlalchemy import case

from helpers.settings import settings
from models.language import Language
from services.crud_service import CrudService


class LocalizedService(CrudService):
    """A resource written once per language, where the language a page is read in decides which of the rows answers for it."""

    # The column naming the same thing across its languages, which is what exactly one row is answered per.
    localized_key: str = ""

    def language_ranking(self, language: str | None):
        """The language asked for wins, the default language of the instance answers when it is missing, and anything published answers before nothing does."""
        wanted = [(Language.code_iso_639_1 == language, 0)] if language else []

        return case(*wanted, (Language.code_iso_639_1 == settings.default_language, len(wanted)), else_=len(wanted) + 1)

    def by_language(self, statement, language: str | None):
        # The shared row is the one carrying no tenant, said as a predicate because PostgreSQL sorts a null above every value and the other two below.
        return statement.outerjoin(Language, Language.id == self.model.language_id).order_by(self.language_ranking(language).asc(), self.model.tenant_id.is_(None), self.model.id.asc())

    def one_per_key(self, rows, ordering: tuple[str, ...]) -> list:
        """One row per key, and the very one that key opens: a card that shows a title and opens another is worse than no card."""
        picked: dict = {}

        for row in rows:
            picked.setdefault(getattr(row, self.localized_key), row)

        return sorted(picked.values(), key=lambda row: tuple(getattr(row, name) for name in ordering))
