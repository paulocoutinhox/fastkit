from datetime import datetime, timezone
from typing import Any

from fastkit_core.context.request import get_request_context
from fastkit_core.errors.exceptions import FastKitError, FieldError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_meta(extra: dict | None = None) -> dict:
    context = get_request_context()

    meta = {"request_id": context.request_id, "timestamp": _now_iso()}

    if extra:
        meta.update(extra)

    return meta


def build_message(code: str | None, text: str | None) -> dict | None:
    if code is None and text is None:
        return None

    return {"code": code, "text": text}


def success_envelope(data: Any = None, message: dict | None = None, meta_extra: dict | None = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "errors": [],
        "meta": _base_meta(meta_extra),
    }


def _serialize_field_error(item: FieldError) -> dict:
    return {
        "field": item.field,
        "path": item.path or [item.field],
        "code": item.code,
        "message": item.message,
        "params": item.params,
    }


def error_envelope(error: FastKitError, error_id: str | None = None, text: str | None = None, request_id: str | None = None) -> dict:
    code = error.error_code

    meta_extra = {}

    if error_id is not None:
        meta_extra["error_id"] = error_id

    if request_id is not None:
        meta_extra["request_id"] = request_id

    return {
        "success": False,
        "message": build_message(code.code, text or error.message),
        "data": None,
        "errors": [_serialize_field_error(item) for item in error.field_errors],
        "meta": _base_meta(meta_extra),
    }
