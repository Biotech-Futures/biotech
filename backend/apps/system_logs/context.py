"""The request a log line was written during, for System Logs.

``RequestContextMiddleware`` remembers the current request and its request id
in context variables (which follow the request through threads and async
code). The log handler reads them when a record is emitted, still in the
request's own thread; nothing here is read by the background writer.
"""
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_MAX_CHARS = 64

_current_request: ContextVar = ContextVar("system_log_request", default=None)
_current_request_id: ContextVar[str] = ContextVar("system_log_request_id", default="")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def current_request():
    return _current_request.get()


def current_request_id() -> str:
    return _current_request_id.get()


def user_id_of(request) -> int | None:
    """The signed-in user's id, if ``request``'s user is already known.

    DRF authenticates inside the view and then sets the user on the underlying
    Django request, so a line logged after that point finds them here. A user
    Django hasn't loaded yet is left unknown rather than loaded: a log call must
    never query the database.
    """
    from django.utils.functional import LazyObject, empty

    user = getattr(request, "__dict__", {}).get("user")
    if isinstance(user, LazyObject):
        if user._wrapped is empty:
            return None
        user = user._wrapped
    if user is not None and getattr(user, "is_authenticated", False):
        return user.pk
    return None


def _request_id_from(request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    incoming = "".join(ch for ch in incoming if ch.isprintable())[:REQUEST_ID_MAX_CHARS]
    return incoming or new_request_id()


class RequestContextMiddleware:
    """Remembers each request, and gives it a request id (the client's
    ``X-Request-ID`` if it sent one), for the duration of the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = _request_id_from(request)
        # Also on the request: Django logs a failed response after the
        # middleware has finished, when the context below is already gone.
        request.system_log_request_id = request_id
        request_token = _current_request.set(request)
        id_token = _current_request_id.set(request_id)
        try:
            return self.get_response(request)
        finally:
            try:
                _current_request_id.reset(id_token)
                _current_request.reset(request_token)
            except ValueError:
                # Reset from another context (a sync/async hand-off): that
                # context is discarded with the request anyway.
                pass
