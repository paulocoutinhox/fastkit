from datetime import datetime, timezone

from fastkit_reports.contracts import ReportRegistry, ReportResult
from fastkit_reports.models import ExecutionStatus, ReportExecution


class ReportService:
    """Runs report definitions and renders them, tracking execution rows for heavy runs."""

    def __init__(self, database, registry: ReportRegistry, renderers: dict, clock=None):
        self._database = database
        self._registry = registry
        self._renderers = renderers
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def add_renderer(self, renderer) -> None:
        self._renderers[renderer.name] = renderer

    def export_formats(self) -> list[str]:
        return [name for name in self._renderers if name not in ("screen", "json")]

    async def build_result(
        self, name: str, session, params: dict | None = None
    ) -> ReportResult:
        definition = self._registry.get(name)
        rows = await definition.query(session, params or {})

        return ReportResult(definition=definition, rows=rows)

    async def resolve_options(
        self, name: str, session, field: str, params: dict | None = None, locale=None
    ) -> list[dict]:
        definition = self._registry.get(name)
        handler = definition.options.get(field)

        if handler is None:
            raise KeyError(f"report '{name}' has no options handler for '{field}'")

        return await handler(session, params or {}, locale)

    async def render(
        self, name: str, session, renderer_name: str, params: dict | None = None
    ):
        result = await self.build_result(name, session, params)
        renderer = self._renderers.get(renderer_name)

        if renderer is None:
            raise KeyError(f"report renderer '{renderer_name}' is not registered")

        return renderer.render(result)

    async def execute(
        self,
        name: str,
        renderer_name: str,
        params: dict | None = None,
        tenant_id: int | None = None,
        requested_by_id=None,
    ) -> ReportExecution:
        execution = ReportExecution(
            report_name=name,
            parameters=params,
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
            status=ExecutionStatus.running.value,
            started_at=self._clock(),
        )

        async with self._database.session_factory() as session:
            session.add(execution)
            await session.commit()
            await session.refresh(execution)

        try:
            async with self._database.session_factory() as session:
                result = await self.build_result(name, session, params)

            if renderer_name not in self._renderers:
                raise KeyError(f"report renderer '{renderer_name}' is not registered")
        except Exception as error:
            return await self._finish_failed(execution.id, error)

        return await self._finish_succeeded(execution.id, len(result.rows))

    async def _finish_succeeded(self, execution_id, row_count: int) -> ReportExecution:
        async with self._database.session_factory() as session:
            execution = await session.get(ReportExecution, execution_id)
            execution.status = ExecutionStatus.succeeded.value
            execution.row_count = row_count
            execution.progress = 100
            execution.finished_at = self._clock()
            await session.commit()
            await session.refresh(execution)

            return execution

    async def _finish_failed(self, execution_id, error: Exception) -> ReportExecution:
        async with self._database.session_factory() as session:
            execution = await session.get(ReportExecution, execution_id)
            execution.status = ExecutionStatus.failed.value
            execution.error_code = "report.failed"
            execution.error_message = str(error)
            execution.finished_at = self._clock()
            await session.commit()
            await session.refresh(execution)

            return execution
