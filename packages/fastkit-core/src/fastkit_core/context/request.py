import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class RequestContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    locale: str = "en"
    tenant_id: int | None = None
    user_id: str | None = None
    trace_id: str | None = None


_current_request: ContextVar[RequestContext | None] = ContextVar("fastkit_request_context", default=None)


def get_request_context() -> RequestContext:
    context = _current_request.get()

    if context is None:
        return RequestContext()

    return context


def set_request_context(context: RequestContext):
    return _current_request.set(context)


def update_request_context(**changes):
    updated = replace(get_request_context(), **changes)

    return _current_request.set(updated), updated


def reset_request_context(token):
    _current_request.reset(token)
