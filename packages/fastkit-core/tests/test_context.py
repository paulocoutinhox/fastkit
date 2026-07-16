from fastkit_core.context.request import (
    RequestContext,
    get_request_context,
    reset_request_context,
    set_request_context,
    update_request_context,
)


def test_default_context_when_unset():
    context = get_request_context()

    assert isinstance(context, RequestContext)
    assert context.locale == "en"


def test_set_and_reset():
    token = set_request_context(RequestContext(request_id="a", locale="pt"))

    try:
        assert get_request_context().request_id == "a"
        assert get_request_context().locale == "pt"
    finally:
        reset_request_context(token)

    assert get_request_context().request_id != "a"


def test_update_context_merges():
    token = set_request_context(RequestContext(request_id="a", locale="en"))

    try:
        _, updated = update_request_context(tenant_id=5)

        assert updated.tenant_id == 5
        assert updated.request_id == "a"
        assert get_request_context().tenant_id == 5
    finally:
        reset_request_context(token)
