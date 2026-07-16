from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from fastkit_core.context.middleware import RequestContextMiddleware
from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.errors.handlers import (
    fastkit_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from fastkit_core.runtime import Runtime


class FastKit:
    """Public facade that bootstraps a Runtime and wires it into a FastAPI application."""

    def __init__(self, settings, installed_apps: list[str] | None = None):
        resolved = installed_apps if installed_apps is not None else list(getattr(settings, "installed_apps", []))

        self.settings = settings
        self.runtime = Runtime(settings=settings, installed_apps=resolved)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        await self.runtime.start()

        try:
            yield
        finally:
            await self.runtime.stop()

    def install(self, app: FastAPI) -> None:
        self.runtime.bootstrap()

        app.state.fastkit = self.runtime

        app.add_middleware(RequestContextMiddleware)

        app.add_exception_handler(RequestValidationError, validation_exception_handler)
        app.add_exception_handler(FastKitError, fastkit_exception_handler)
        app.add_exception_handler(Exception, unhandled_exception_handler)

        for router, prefix, tags, _ in self.runtime.routers.all():
            app.include_router(router, prefix=prefix, tags=tags)


def create_application(settings, installed_apps: list[str] | None = None) -> FastAPI:
    kit = FastKit(settings=settings, installed_apps=installed_apps)

    app = FastAPI(
        title=getattr(getattr(settings, "app", None), "name", "FastKit"),
        lifespan=kit.lifespan,
    )

    kit.install(app)
    app.state.fastkit_facade = kit

    return app
