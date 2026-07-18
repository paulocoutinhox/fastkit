import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from fastkit_core.app import FastKit, create_application
from fastkit_core.apps.base import FastKitApp
from fastkit_core.context.middleware import REQUEST_ID_HEADER
from fastkit_core.registries.components import (
    ModelRegistry,
    RouterRegistry,
    TemplateRegistry,
)


def client_for(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_request_id_header_roundtrip(error_app):
    response = client_for(error_app).get(
        "/ok", headers={REQUEST_ID_HEADER: "custom-id"}
    )

    assert response.headers[REQUEST_ID_HEADER] == "custom-id"


def test_request_id_generated_when_absent(error_app):
    assert client_for(error_app).get("/ok").headers[REQUEST_ID_HEADER]


def test_validation_error_is_normalized(error_app):
    response = client_for(error_app).post("/validate", json={"age": "abc"})
    body = response.json()

    assert response.status_code == 422
    assert body["success"] is False
    assert body["message"]["code"] == "validation.failed"
    assert body["errors"][0]["code"] == "validation.integer-invalid"
    assert body["errors"][0]["field"] == "age"


def test_missing_body_field_maps_to_required(error_app):
    response = client_for(error_app).post("/validate", json={})

    assert response.json()["errors"][0]["code"] == "validation.required"


def test_unknown_route_is_enveloped(error_app):
    response = client_for(error_app).get("/does-not-exist")
    body = response.json()

    assert response.status_code == 404
    assert body["success"] is False
    assert body["message"]["code"] == "resource.not_found"
    assert body["message"]["text"]
    assert body["errors"] == []


def test_method_not_allowed_is_enveloped_with_allow_header(error_app):
    response = client_for(error_app).post("/ok")
    body = response.json()

    assert response.status_code == 405
    assert body["message"]["code"] == "http.method_not_allowed"
    assert "allow" in {key.lower() for key in response.headers}


def test_unmapped_http_exception_keeps_status_and_generic_code(error_app):
    response = client_for(error_app).get("/teapot")
    body = response.json()

    assert response.status_code == 418
    assert body["message"]["code"] == "http.error"
    assert body["message"]["text"]


def test_fastkit_error_envelope(error_app):
    response = client_for(error_app).get("/missing")
    body = response.json()

    assert response.status_code == 404
    assert body["message"]["code"] == "resource.not_found"
    assert body["message"]["text"] == "gone"


def test_unhandled_error_is_masked(error_app):
    response = client_for(error_app).get(
        "/boom", headers={REQUEST_ID_HEADER: "trace-500"}
    )
    body = response.json()

    assert response.status_code == 500
    assert body["message"]["code"] == "internal.error"
    assert body["message"]["text"] == "Something went wrong. Please try again."
    assert body["meta"]["error_id"].startswith("ERR-")
    assert body["meta"]["request_id"] == "trace-500"


class _FakeRuntime:
    def __init__(self, translator=None, resolver=None):
        self._components = {"translator": translator, "locale_resolver": resolver}

    def try_component(self, name):
        return self._components.get(name)


class _Translator:
    def __init__(self, catalog):
        self._catalog = catalog

    def gettext(self, key, locale=None, **params):
        text = self._catalog.get((key, locale), self._catalog.get(key, key))

        return text.format(**params) if params else text


class _Resolver:
    def resolve(self, accept_language=None):
        return "pt" if accept_language else "en"


def _app_with_runtime(runtime):
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from fastkit_core.context.middleware import RequestContextMiddleware
    from fastkit_core.errors.codes import CACHE_ERROR, RESOURCE_NOT_FOUND
    from fastkit_core.errors.exceptions import FastKitError, NotFoundError
    from fastkit_core.errors.handlers import (
        fastkit_exception_handler,
        http_exception_handler,
        unhandled_exception_handler,
        validation_exception_handler,
    )

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastKitError, fastkit_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.state.fastkit = runtime

    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    @router.get("/lookup")
    async def lookup():
        raise NotFoundError(RESOURCE_NOT_FOUND)

    @router.get("/cache-boom")
    async def cache_boom():
        raise FastKitError(CACHE_ERROR, message="internal cache host down at 10.0.0.5")

    @router.get("/field-error")
    async def field_error():
        from fastkit_core.errors.codes import VALIDATION_FAILED
        from fastkit_core.errors.exceptions import FieldError, ValidationError

        raise ValidationError(
            VALIDATION_FAILED,
            field_errors=[
                FieldError(
                    "password",
                    "validation.password-too-short",
                    params={"min_length": 8},
                )
            ],
        )

    app.include_router(router)

    return app


def test_error_text_is_translated_from_runtime():
    runtime = _FakeRuntime(
        translator=_Translator({("error.internal", "pt"): "Algo deu errado."}),
        resolver=_Resolver(),
    )
    response = client_for(_app_with_runtime(runtime)).get(
        "/boom", headers={"Accept-Language": "pt-BR"}
    )

    assert response.json()["message"]["text"] == "Algo deu errado."


def test_error_text_falls_back_to_generic_when_no_translation():
    runtime = _FakeRuntime(translator=_Translator({}))
    response = client_for(_app_with_runtime(runtime)).get("/lookup")

    assert (
        response.json()["message"]["text"] == "Something went wrong. Please try again."
    )


def test_error_text_falls_back_to_generic_when_no_translator():
    response = client_for(_app_with_runtime(_FakeRuntime())).get("/lookup")

    assert (
        response.json()["message"]["text"] == "Something went wrong. Please try again."
    )


def test_field_error_messages_are_translated_with_params():
    runtime = _FakeRuntime(
        translator=_Translator(
            {
                (
                    "validation.password-too-short",
                    "pt",
                ): "A senha deve ter pelo menos {min_length} caracteres."
            }
        ),
        resolver=_Resolver(),
    )
    response = client_for(_app_with_runtime(runtime)).get(
        "/field-error", headers={"Accept-Language": "pt-BR"}
    )
    body = response.json()

    assert body["errors"][0]["code"] == "validation.password-too-short"
    assert body["errors"][0]["message"] == "A senha deve ter pelo menos 8 caracteres."


def test_non_user_visible_error_never_leaks_its_message():
    runtime = _FakeRuntime(
        translator=_Translator({("error.internal", "en"): "Generic problem."}),
        resolver=_Resolver(),
    )
    response = client_for(_app_with_runtime(runtime)).get("/cache-boom")

    assert response.json()["message"]["text"] == "Generic problem."


def test_http_error_text_is_translated_from_runtime():
    runtime = _FakeRuntime(
        translator=_Translator({("error.not-found", "pt"): "Não encontrado."}),
        resolver=_Resolver(),
    )
    response = client_for(_app_with_runtime(runtime)).get(
        "/nope", headers={"Accept-Language": "pt-BR"}
    )

    assert response.status_code == 404
    assert response.json()["message"]["text"] == "Não encontrado."


def test_error_code_for_status_maps_and_falls_back():
    from fastkit_core.errors.handlers import error_code_for_status

    assert error_code_for_status(404).code == "resource.not_found"
    assert error_code_for_status(418).code == "http.error"
    assert error_code_for_status(500).code == "internal.error"
    assert error_code_for_status(599).code == "internal.error"


class DemoApp(FastKitApp):
    name = "demo"

    def register_routers(self, context):
        router = APIRouter()

        @router.get("/demo/ping")
        async def ping():
            return {"pong": True}

        context.routers.include(router, source="demo")
        context.set_component("marker", "installed")


class DemoSettings:
    class app:
        name = "Demo"

    installed_apps = ["demo"]


def test_create_application_mounts_apps(monkeypatch):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"demo": DemoApp})

    app = create_application(DemoSettings())
    client = TestClient(app)

    assert client.get("/demo/ping").json() == {"pong": True}
    assert app.state.fastkit.component("marker") == "installed"
    assert isinstance(app.state.fastkit_facade, FastKit)


async def test_fastkit_lifespan_runs(monkeypatch):
    started: list[str] = []

    class LifeApp(FastKitApp):
        name = "life"

        async def startup(self, context):
            started.append("up")

        async def shutdown(self, context):
            started.append("down")

    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"life": LifeApp})

    kit = FastKit(settings=DemoSettings(), installed_apps=["life"])
    app = FastAPI(lifespan=kit.lifespan)
    kit.install(app)

    with TestClient(app):
        pass

    assert started == ["up", "down"]


def test_component_registries_behaviour():
    models = ModelRegistry()

    class Thing:
        pass

    models.register(Thing, source="x")
    assert Thing in models.all()
    assert list(models.sources().values()) == ["x"]

    with pytest.raises(ValueError, match="already registered by 'x', now by 'y'"):
        models.register(Thing, source="y")

    routers = RouterRegistry()
    routers.include(APIRouter(), prefix="/x", source="y")
    assert len(routers.all()) == 1

    templates = TemplateRegistry()
    templates.add_directory("/tpl", priority=10, source="project")
    templates.add_package("fastkit_mail", "templates", priority=5, source="mail")
    templates.add_override("accounts.welcome", "emails/welcome")

    assert templates.directories()[0].path == "/tpl"
    assert templates.packages()[0].package == "fastkit_mail"
    assert templates.overrides["accounts.welcome"] == "emails/welcome"
