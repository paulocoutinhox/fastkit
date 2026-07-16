import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from fastkit_core.context.request import RequestContext, reset_request_context, set_request_context

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Installs a per-request context with a stable request id exposed as a response header."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        context = RequestContext(request_id=request_id)
        token = set_request_context(context)

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_context(token)
