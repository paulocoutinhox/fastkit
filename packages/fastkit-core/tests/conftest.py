import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from fastkit_core.context.middleware import RequestContextMiddleware
from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import FastKitError, NotFoundError
from fastkit_core.errors.handlers import (
    fastkit_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


class Payload(BaseModel):
    age: int


def make_error_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(FastKitError, fastkit_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    router = APIRouter()

    @router.get("/ok")
    async def ok():
        return {"ok": True}

    @router.post("/validate")
    async def validate(payload: Payload):
        return {"age": payload.age}

    @router.get("/missing")
    async def missing():
        raise NotFoundError(RESOURCE_NOT_FOUND, message="gone")

    @router.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    app.include_router(router)

    return app


@pytest.fixture
def error_app() -> FastAPI:
    return make_error_app()
