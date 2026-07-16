from fastkit_core.api.envelope import build_message, error_envelope, success_envelope
from fastkit_core.api.pagination import CursorPage, OffsetPage, clamp_page_size
from fastkit_core.context.request import RequestContext, reset_request_context, set_request_context
from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import FastKitError, FieldError


def test_success_envelope_defaults():
    envelope = success_envelope()

    assert envelope["success"] is True
    assert envelope["data"] == {}
    assert envelope["message"] is None
    assert envelope["errors"] == []
    assert "request_id" in envelope["meta"]
    assert "timestamp" in envelope["meta"]


def test_success_envelope_with_message_and_data():
    envelope = success_envelope(data={"id": "1"}, message=build_message("users.created", "Created."), meta_extra={"pagination": {}})

    assert envelope["data"] == {"id": "1"}
    assert envelope["message"] == {"code": "users.created", "text": "Created."}
    assert envelope["meta"]["pagination"] == {}


def test_build_message_returns_none_when_empty():
    assert build_message(None, None) is None
    assert build_message("code", None) == {"code": "code", "text": None}


def test_error_envelope_serializes_field_errors():
    error = FastKitError(RESOURCE_NOT_FOUND, message="missing", field_errors=[FieldError("email", "validation.required", "Required", ["email"])])
    envelope = error_envelope(error, error_id="ERR-1")

    assert envelope["success"] is False
    assert envelope["message"] == {"code": "resource.not_found", "text": "missing"}
    assert envelope["errors"][0]["field"] == "email"
    assert envelope["errors"][0]["path"] == ["email"]
    assert envelope["meta"]["error_id"] == "ERR-1"


def test_error_envelope_field_path_defaults_to_field():
    error = FastKitError(RESOURCE_NOT_FOUND, field_errors=[FieldError("name", "code", "msg")])
    envelope = error_envelope(error)

    assert envelope["errors"][0]["path"] == ["name"]


def test_request_context_is_used_in_meta():
    token = set_request_context(RequestContext(request_id="fixed"))

    try:
        assert success_envelope()["meta"]["request_id"] == "fixed"
    finally:
        reset_request_context(token)


def test_offset_page_meta():
    page = OffsetPage(page=2, page_size=25, total_items=100)
    meta = page.to_meta()

    assert meta["total_pages"] == 4
    assert meta["has_previous"] is True
    assert meta["has_next"] is True
    assert meta["strategy"] == "offset"


def test_offset_page_zero_size():
    assert OffsetPage(page=1, page_size=0, total_items=10).total_pages == 0


def test_cursor_page_meta():
    meta = CursorPage(next_cursor="next", previous_cursor=None).to_meta()

    assert meta["has_next"] is True
    assert meta["has_previous"] is False


def test_clamp_page_size():
    assert clamp_page_size(0, default=25, maximum=100) == 25
    assert clamp_page_size(500, default=25, maximum=100) == 100
    assert clamp_page_size(50, default=25, maximum=100) == 50
