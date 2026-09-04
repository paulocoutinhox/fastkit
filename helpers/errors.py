"""What a failure is, and the one shape every one of them reaches a caller in."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from helpers.i18n import translate

VALIDATION_MESSAGES = {
    "missing": "validation.required",
    "string_too_short": "validation.string-too-short",
    "string_too_long": "validation.string-too-long",
    "string_pattern_mismatch": "validation.invalid-format",
    "greater_than": "validation.value-too-small",
    "greater_than_equal": "validation.value-too-small",
    "less_than": "validation.value-too-large",
    "less_than_equal": "validation.value-too-large",
    "enum": "validation.invalid-option",
    "datetime_from_date_parsing": "validation.invalid-datetime",
    "datetime_parsing": "validation.invalid-datetime",
    "date_parsing": "validation.invalid-date",
    "date_from_datetime_parsing": "validation.invalid-date",
    "int_parsing": "validation.invalid-number",
    "float_parsing": "validation.invalid-number",
    "bool_parsing": "validation.invalid-boolean",
    "json_invalid": "validation.invalid-json",
    "extra_forbidden": "validation.unknown-field",
}

HTTP_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "error.bad-request",
    status.HTTP_401_UNAUTHORIZED: "error.unauthorized",
    status.HTTP_403_FORBIDDEN: "error.forbidden",
    status.HTTP_404_NOT_FOUND: "error.not-found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "error.method-not-allowed",
    status.HTTP_409_CONFLICT: "error.conflict",
    status.HTTP_413_CONTENT_TOO_LARGE: "error.upload-too-large",
    status.HTTP_429_TOO_MANY_REQUESTS: "error.rate-limited",
}

logger = logging.getLogger(__name__)


class AppError(Exception):
    """A domain failure carrying a translation key, so the message is rendered in the caller language."""

    def __init__(self, code: str, status_code: int = status.HTTP_400_BAD_REQUEST, field: str | None = None, **params):
        super().__init__(code)

        self.code = code
        self.status_code = status_code
        self.field = field
        self.params = params

    @property
    def message(self) -> str:
        return translate(self.code, **self.params)


class NotFoundError(AppError):
    def __init__(self, code: str = "error.not-found", **params):
        super().__init__(code, status.HTTP_404_NOT_FOUND, **params)


class ConflictError(AppError):
    def __init__(self, code: str, field: str | None = None, **params):
        super().__init__(code, status.HTTP_409_CONFLICT, field, **params)


class ValidationError(AppError):
    def __init__(self, code: str, field: str | None = None, **params):
        super().__init__(code, status.HTTP_422_UNPROCESSABLE_CONTENT, field, **params)


class AuthenticationError(AppError):
    def __init__(self, code: str = "error.unauthorized", **params):
        super().__init__(code, status.HTTP_401_UNAUTHORIZED, **params)


class PermissionError(AppError):
    def __init__(self, code: str = "error.forbidden", **params):
        super().__init__(code, status.HTTP_403_FORBIDDEN, **params)


def build_payload(code: str, message: str, errors: dict[str, str] | None = None) -> dict:
    return {"code": code, "detail": message, "errors": errors or {}}


def field_name(name: str) -> str:
    """The client marks the field by the name it sent, and that name is the camelCase alias of the schema."""
    return ".".join(to_camel(part) if "_" in part else part for part in name.split("."))


def validation_message(error: dict) -> str:
    """A field validator that raised carries its own message, already in the caller language, and that one answers instead of a generic stand in."""
    context = error.get("ctx", {})

    if "error" in context:
        return str(context["error"])

    # Asking for at least one character is asking for something rather than nothing, and a blank field is told that and not a length.
    if error["type"] == "string_too_short" and context.get("min_length") == 1:
        return translate("validation.blank")

    return translate(VALIDATION_MESSAGES.get(error["type"], "validation.invalid"), **context)


def field_path(location: tuple) -> str:
    """The first segment names the request part, so the field is what follows it."""
    parts = [str(part) for part in location[1:]] or [str(part) for part in location]

    return field_name(".".join(parts))


def setup(app: FastAPI, drawn_not_found=None, drawn_error=None):
    """The site draws its own pages for an address that names nothing and for a request that broke, and both are handed in rather than reached for."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        message = exc.message
        errors = {field_name(exc.field): message} if exc.field else {}

        return JSONResponse(status_code=exc.status_code, content=build_payload(exc.code, message, errors))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # A segment of an address that cannot name a record is a page that does not exist, and the site draws that page.
        if drawn_not_found is not None and any(error["loc"][:1] == ("path",) for error in exc.errors()):
            drawn = await drawn_not_found(request)

            if drawn is not None:
                return drawn

        errors = {}

        for error in exc.errors():
            errors[field_path(error["loc"])] = validation_message(error)

        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=build_payload("error.validation", translate("error.validation"), errors))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = HTTP_MESSAGES.get(exc.status_code, "error.internal")

        return JSONResponse(status_code=exc.status_code, content=build_payload(code, translate(code)), headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)

        if drawn_error is not None:
            # Whatever broke may be the very thing a page needs to be drawn, and a handler that raises answers a body of nothing.
            try:
                drawn = await drawn_error(request)
            except Exception:
                logger.exception("The error page could not be drawn either")
            else:
                if drawn is not None:
                    return drawn

        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=build_payload("error.internal", translate("error.internal")))
