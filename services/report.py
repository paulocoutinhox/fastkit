from dataclasses import replace
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user_role import UserRole
from helpers.brand import Brand
from helpers.dates import now
from helpers.i18n import current_locale, translate
from helpers.not_found_error import NotFoundError
from helpers.scope import belongs_to_tenant
from helpers.validation_error import ValidationError
from models.user import User
from schemas.base_schema import BaseSchema
from services.access_rule import AccessRule
from services.has_role import HasRole
from services.report_chart import ReportChart
from services.report_column import ReportColumn
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter

# How many rows a screen draws and a file carries at most, past which the filter is narrowed instead of the answer cut short in silence.
ROW_LIMIT = 5000


class Report:
    """A filtered reading of the data that an operator asks for on a screen of the panel and takes away as a file, which every report of the application subclasses."""

    # The segment of the address the report answers at, and the name its catalogue keys are written under.
    code: str = ""

    # The catalogue key of its title.
    title: str = ""

    # What the filter accepts, which is read off the query string through the same rules every payload of the API is.
    filters: type[BaseSchema] | None = None

    columns: tuple[ReportColumn, ...] = ()

    # What is drawn above the rows, on the screen, on the printed page and in the spreadsheet alike.
    charts: tuple[ReportChart, ...] = ()

    # Who reaches it, which nobody but an administrator does until the report says otherwise.
    access: AccessRule = HasRole(UserRole.ADMINISTRATOR)

    # The formats it can be taken away in, and none means it is only read on the screen.
    exporters: tuple[ReportExporter, ...] = ()

    row_limit: int = ROW_LIMIT

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # A report missing any of these is a screen nobody can address, title, filter or fill, so it fails where it is written and never in front of an operator.
        if not (cls.code and cls.title and cls.filters and cls.columns) or not callable(getattr(cls, "statement", None)):
            raise TypeError(f"{cls.__name__} declares a code, a title, its filters and its columns, and the statement that reads its rows")

        # A chart is named by its key on the screen and in the file, so two that share one would draw over each other.
        if len({chart.key for chart in cls.charts}) != len(cls.charts):
            raise TypeError(f"{cls.__name__} names each of its charts by a key of its own")

        for chart in cls.charts:
            chart.check(cls.columns)

    def default_filter(self, operator: User) -> BaseSchema | None:
        """The filter the screen opens already applied for this operator, and none means it waits for them to choose one."""
        return None

    async def details(self, db: AsyncSession, chosen: BaseSchema, operator: User, document: ReportDocument) -> dict:
        """Whatever else a run answers beside its rows and charts, for a screen, a template or a format a report draws on its own, which is nothing until a report says otherwise."""
        return {}

    def exporter(self, code: str) -> ReportExporter:
        for exporter in self.exporters:
            if exporter.code == code:
                return exporter

        raise NotFoundError()

    def confined(self, statement: Select, column, operator: User) -> Select:
        """What an operator of one brand reads is that brand alone, the way every listing of the panel is."""
        if operator.tenant_id is None:
            return statement

        return statement.where(belongs_to_tenant(column, operator.tenant_id))

    def midnight(self, day: date, operator: User) -> datetime:
        """Where a day of a filter starts, which is on the clock of the operator who chose it."""
        return datetime.combine(day, time.min, tzinfo=ZoneInfo(operator.timezone))

    async def rows(self, db: AsyncSession, chosen: BaseSchema, operator: User) -> list[dict]:
        statement = self.statement(chosen, operator).limit(self.row_limit + 1)
        rows = [dict(row._mapping) for row in await db.execute(statement)]

        # A file that silently stops at the limit reads as everything there is, so a filter that reaches past it is sent back to be narrowed.
        if len(rows) > self.row_limit:
            raise ValidationError("error.report-too-large", limit=self.row_limit)

        return rows

    def document(self, rows: list[dict], operator: User, brand: Brand) -> ReportDocument:
        document = ReportDocument(title=translate(self.title), brand_name=brand.name, brand_code=brand.code, generated_at=now(), columns=self.columns, rows=rows, locale=current_locale.get(), zone=operator.timezone)

        return replace(document, plots=tuple(plot for chart in self.charts for plot in chart.plots(document)))
