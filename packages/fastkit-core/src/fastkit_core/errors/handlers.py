import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from fastkit_core.api.envelope import error_envelope
from fastkit_core.errors.codes import (
    AUTHENTICATION_REQUIRED,
    AUTHORIZATION_DENIED,
    BAD_REQUEST,
    CONFLICT_STATE,
    ErrorCode,
    HTTP_ERROR,
    INTERNAL_ERROR,
    METHOD_NOT_ALLOWED,
    NOT_ACCEPTABLE,
    PAYLOAD_TOO_LARGE,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    RATE_LIMIT_EXCEEDED,
    RESOURCE_NOT_FOUND,
    UNSUPPORTED_MEDIA_TYPE,
    VALIDATION_FAILED,
)
from fastkit_core.errors.exceptions import FastKitError, FieldError, ValidationError

logger = logging.getLogger("fastkit.errors")


PYDANTIC_CODE_MAP = {
    "no_such_attribute": "validation.invalid",
    "json_invalid": "validation.json-invalid",
    "json_type": "validation.json-invalid",
    "needs_python_object": "validation.invalid",
    "recursion_loop": "validation.recursion",
    "missing": "validation.required",
    "frozen_field": "validation.frozen",
    "frozen_instance": "validation.frozen",
    "extra_forbidden": "validation.extra-forbidden",
    "invalid_key": "validation.invalid-key",
    "get_attribute_error": "validation.invalid",
    "model_type": "validation.dict-type",
    "model_attributes_type": "validation.dict-type",
    "dataclass_type": "validation.dict-type",
    "dataclass_exact_type": "validation.dict-type",
    "default_factory_not_called": "validation.invalid",
    "none_required": "validation.none-required",
    "greater_than": "validation.number-greater-than",
    "greater_than_equal": "validation.number-greater-or-equal",
    "less_than": "validation.number-less-than",
    "less_than_equal": "validation.number-less-or-equal",
    "multiple_of": "validation.number-multiple-of",
    "finite_number": "validation.number-finite",
    "too_short": "validation.too-short",
    "too_long": "validation.too-long",
    "iterable_type": "validation.list-type",
    "iteration_error": "validation.invalid",
    "string_type": "validation.string-type",
    "string_sub_type": "validation.string-type",
    "string_unicode": "validation.string-type",
    "string_too_short": "validation.string-too-short",
    "string_too_long": "validation.string-too-long",
    "string_pattern_mismatch": "validation.string-pattern",
    "string_not_ascii": "validation.string-ascii",
    "enum": "validation.enum",
    "dict_type": "validation.dict-type",
    "mapping_type": "validation.dict-type",
    "list_type": "validation.list-type",
    "tuple_type": "validation.list-type",
    "set_type": "validation.list-type",
    "set_item_not_hashable": "validation.invalid",
    "bool_type": "validation.boolean-invalid",
    "bool_parsing": "validation.boolean-invalid",
    "int_type": "validation.integer-type",
    "int_parsing": "validation.integer-invalid",
    "int_parsing_size": "validation.integer-invalid",
    "int_from_float": "validation.integer-invalid",
    "float_type": "validation.number-type",
    "float_parsing": "validation.number-invalid",
    "bytes_type": "validation.bytes-type",
    "bytes_too_short": "validation.bytes-too-short",
    "bytes_too_long": "validation.bytes-too-long",
    "bytes_invalid_encoding": "validation.bytes-encoding",
    "value_error": "validation.invalid",
    "assertion_error": "validation.invalid",
    "literal_error": "validation.literal",
    "missing_sentinel_error": "validation.invalid",
    "date_type": "validation.date-invalid",
    "date_parsing": "validation.date-invalid",
    "date_from_datetime_parsing": "validation.date-invalid",
    "date_from_datetime_inexact": "validation.date-invalid",
    "date_past": "validation.date-past",
    "date_future": "validation.date-future",
    "time_type": "validation.time-invalid",
    "time_parsing": "validation.time-invalid",
    "datetime_type": "validation.datetime-invalid",
    "datetime_parsing": "validation.datetime-invalid",
    "datetime_object_invalid": "validation.datetime-invalid",
    "datetime_from_date_parsing": "validation.datetime-invalid",
    "datetime_past": "validation.datetime-past",
    "datetime_future": "validation.datetime-future",
    "timezone_naive": "validation.timezone-naive",
    "timezone_aware": "validation.timezone-aware",
    "timezone_offset": "validation.timezone-offset",
    "time_delta_type": "validation.duration-invalid",
    "time_delta_parsing": "validation.duration-invalid",
    "frozen_set_type": "validation.list-type",
    "is_instance_of": "validation.invalid",
    "is_subclass_of": "validation.invalid",
    "callable_type": "validation.invalid",
    "union_tag_invalid": "validation.union-tag",
    "union_tag_not_found": "validation.union-tag",
    "arguments_type": "validation.invalid",
    "missing_argument": "validation.required",
    "unexpected_keyword_argument": "validation.extra-forbidden",
    "missing_keyword_only_argument": "validation.required",
    "unexpected_positional_argument": "validation.extra-forbidden",
    "missing_positional_only_argument": "validation.required",
    "multiple_argument_values": "validation.invalid",
    "url_type": "validation.url-invalid",
    "url_parsing": "validation.url-invalid",
    "url_syntax_violation": "validation.url-invalid",
    "url_too_long": "validation.url-invalid",
    "url_scheme": "validation.url-scheme",
    "uuid_type": "validation.uuid-invalid",
    "uuid_parsing": "validation.uuid-invalid",
    "uuid_version": "validation.uuid-invalid",
    "decimal_type": "validation.decimal-invalid",
    "decimal_parsing": "validation.decimal-invalid",
    "decimal_max_digits": "validation.decimal-max-digits",
    "decimal_max_places": "validation.decimal-max-places",
    "decimal_whole_digits": "validation.decimal-whole-digits",
    "complex_type": "validation.number-type",
    "complex_str_parsing": "validation.number-invalid",
}

GENERIC_VALIDATION_CODE = "validation.invalid"
GENERIC_ERROR_FALLBACK = "Something went wrong. Please try again."

HTTP_STATUS_CODE_MAP = {
    400: BAD_REQUEST,
    401: AUTHENTICATION_REQUIRED,
    403: AUTHORIZATION_DENIED,
    404: RESOURCE_NOT_FOUND,
    405: METHOD_NOT_ALLOWED,
    406: NOT_ACCEPTABLE,
    409: CONFLICT_STATE,
    413: PAYLOAD_TOO_LARGE,
    415: UNSUPPORTED_MEDIA_TYPE,
    429: RATE_LIMIT_EXCEEDED,
    503: PROVIDER_UNAVAILABLE,
    504: PROVIDER_TIMEOUT,
}


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
    """User-facing text always comes from the translated catalog, never the internal detail.

    The inline ``exc.message`` is developer detail and is only used as a fallback when no
    translation is available (no runtime translator), so user text stays a proper localized sentence.
    """

    code = exc.error_code

    if code.user_visible:
        text = translate_error(request, code) or exc.message

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


def error_code_for_status(status_code: int) -> ErrorCode:
    mapped = HTTP_STATUS_CODE_MAP.get(status_code)

    if mapped is not None:
        return mapped

    if status_code >= 500:
        return INTERNAL_ERROR

    return HTTP_ERROR


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    error = FastKitError(error_code_for_status(exc.status_code))
    envelope = error_envelope(error, text=resolve_error_text(request, error))

    return JSONResponse(status_code=exc.status_code, content=envelope, headers=exc.headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = f"ERR-{uuid.uuid4()}"
    logger.critical("unhandled error (%s)", error_id, exc_info=exc)

    error = FastKitError(INTERNAL_ERROR)
    request_id = getattr(request.state, "request_id", None)
    envelope = error_envelope(error, error_id=error_id, text=resolve_error_text(request, error), request_id=request_id)

    return JSONResponse(status_code=INTERNAL_ERROR.http_status, content=envelope)
