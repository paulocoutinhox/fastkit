import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fastkit_core.api.envelope import error_envelope
from fastkit_core.errors.codes import INTERNAL_ERROR, VALIDATION_FAILED
from fastkit_core.errors.exceptions import FastKitError, FieldError, ValidationError

logger = logging.getLogger("fastkit.errors")


PYDANTIC_CODE_MAP = {
    "missing": "validation.required",
    "string_type": "validation.string-type",
    "string_too_short": "validation.string-too-short",
    "string_too_long": "validation.string-too-long",
    "string_pattern_mismatch": "validation.string-pattern",
    "greater_than": "validation.number-greater-than",
    "greater_than_equal": "validation.number-greater-or-equal",
    "less_than": "validation.number-less-than",
    "less_than_equal": "validation.number-less-or-equal",
    "multiple_of": "validation.number-multiple-of",
    "int_parsing": "validation.integer-invalid",
    "int_type": "validation.integer-type",
    "int_from_float": "validation.integer-invalid",
    "float_parsing": "validation.number-invalid",
    "float_type": "validation.number-type",
    "decimal_parsing": "validation.decimal-invalid",
    "decimal_type": "validation.decimal-invalid",
    "bool_parsing": "validation.boolean-invalid",
    "bool_type": "validation.boolean-invalid",
    "date_parsing": "validation.date-invalid",
    "date_type": "validation.date-invalid",
    "date_from_datetime_parsing": "validation.date-invalid",
    "datetime_parsing": "validation.datetime-invalid",
    "datetime_type": "validation.datetime-invalid",
    "datetime_from_date_parsing": "validation.datetime-invalid",
    "time_parsing": "validation.time-invalid",
    "time_type": "validation.time-invalid",
    "uuid_parsing": "validation.uuid-invalid",
    "uuid_type": "validation.uuid-invalid",
    "url_parsing": "validation.url-invalid",
    "url_type": "validation.url-invalid",
    "json_invalid": "validation.json-invalid",
    "json_type": "validation.json-invalid",
    "enum": "validation.enum",
    "literal_error": "validation.literal",
    "list_type": "validation.list-type",
    "dict_type": "validation.dict-type",
    "model_type": "validation.dict-type",
    "extra_forbidden": "validation.extra-forbidden",
    "value_error": "validation.invalid",
}

GENERIC_VALIDATION_CODE = "validation.invalid"
GENERIC_ERROR_FALLBACK = "Something went wrong. Please try again."


def _runtime_translation(request: Request):
    runtime = getattr(request.app.state, "fastkit", None)

    if runtime is None:
        return None, None

    translator = runtime.try_component("translator")

    if translator is None:
        return None, None

    resolver = runtime.try_component("locale_resolver")
    locale = resolver.resolve(accept_language=request.headers.get("accept-language")) if resolver is not None else None

    return translator, locale


def translate_error(request: Request, error_code) -> str | None:
    """Resolve a human message for an error code using the runtime translator, if present."""

    translator, locale = _runtime_translation(request)

    if translator is None:
        return None

    text = translator.gettext(error_code.translation_key, locale=locale)

    return text if text != error_code.translation_key else None


def resolve_error_text(request: Request, exc: FastKitError) -> str:
    """Single source for a user-facing error message: never null, never leaks internal detail."""

    code = exc.error_code

    if code.user_visible:
        text = exc.message or translate_error(request, code)

        if text:
            return text

    return translate_error(request, INTERNAL_ERROR) or GENERIC_ERROR_FALLBACK


def localize_field_errors(request: Request, exc: FastKitError) -> None:
    """Fill each field error's message from the catalog, keyed by its code and params."""

    translator, locale = _runtime_translation(request)

    if translator is None:
        return

    for field_error in exc.field_errors:
        field_error.message = translator.gettext(field_error.code, locale=locale, **field_error.params)


def _field_from_loc(loc: tuple) -> tuple[str, list[str]]:
    parts = [str(item) for item in loc if item not in ("body", "query", "path")]

    if not parts:
        return "__root__", ["__root__"]

    return parts[-1], parts


def _scalar_params(ctx) -> dict:
    return {key: value if isinstance(value, (str, int, float, bool)) else str(value) for key, value in (ctx or {}).items()}


def normalize_validation_error(exc: RequestValidationError) -> ValidationError:
    field_errors: list[FieldError] = []

    for detail in exc.errors():
        field, path = _field_from_loc(tuple(detail.get("loc", ())))
        code = PYDANTIC_CODE_MAP.get(detail.get("type", ""), GENERIC_VALIDATION_CODE)

        field_errors.append(FieldError(field=field, code=code, path=path, params=_scalar_params(detail.get("ctx"))))

    return ValidationError(VALIDATION_FAILED, field_errors=field_errors)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    error = normalize_validation_error(exc)
    localize_field_errors(request, error)
    envelope = error_envelope(error, text=resolve_error_text(request, error))

    return JSONResponse(status_code=VALIDATION_FAILED.http_status, content=envelope)


async def fastkit_exception_handler(request: Request, exc: FastKitError) -> JSONResponse:
    error_id = None

    if exc.error_code.should_log:
        error_id = f"ERR-{uuid.uuid4()}"
        logger.error("fastkit error %s (%s)", exc.error_code.code, error_id, exc_info=exc)

    localize_field_errors(request, exc)
    envelope = error_envelope(exc, error_id=error_id, text=resolve_error_text(request, exc))

    return JSONResponse(status_code=exc.error_code.http_status, content=envelope)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = f"ERR-{uuid.uuid4()}"
    logger.critical("unhandled error (%s)", error_id, exc_info=exc)

    error = FastKitError(INTERNAL_ERROR)
    request_id = getattr(request.state, "request_id", None)
    envelope = error_envelope(error, error_id=error_id, text=resolve_error_text(request, error), request_id=request_id)

    return JSONResponse(status_code=INTERNAL_ERROR.http_status, content=envelope)
