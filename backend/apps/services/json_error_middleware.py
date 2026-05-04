"""Catch-all JSON error middleware.

Backstop for ``apps.services.exception_handler`` — that handler only fires
when the failing view goes through DRF's ``dispatch()``. This middleware
catches everything else: plain Django views, exceptions raised before DRF
dispatch (e.g. inside another middleware that runs *after* this one), and
exceptions raised by the DRF handler itself.

Result: every API request that crashes returns JSON, regardless of which
layer raised. The frontend never sees Django's yellow debug HTML page or
the generic 500 HTML response.

Path-based allowlist
--------------------
Some endpoints are HTML by design (Django admin, Swagger UI, etc.). For
those we deliberately let Django render its native HTML response so the
admin UI still works. Anything not on the allowlist is treated as JSON-only.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Paths whose error responses MUST stay HTML — Django admin, OpenAPI doc UIs,
# browsable DRF login, static/media. Edit when new HTML-by-design routes
# appear in ``config/urls.py``.
HTML_RESPONSE_PREFIXES: tuple[str, ...] = (
    "/admin/",
    "/api/docs/",
    "/api/redoc/",
    "/api/schema/",
    "/api-auth/",
    "/static/",
    "/media/",
)


def _wants_json(request) -> bool:
    """True if the failing request should get a JSON 500 instead of HTML."""
    return not any(request.path.startswith(p) for p in HTML_RESPONSE_PREFIXES)


class JsonErrorMiddleware:
    """Convert uncaught view exceptions on API paths to JSON 500 responses.

    Django calls ``process_exception`` on each middleware in REVERSE
    declaration order until one returns a response. Place this middleware
    at the TOP of ``MIDDLEWARE`` so it runs LAST — letting every other
    middleware decline first — and acts as the final safety net.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not _wants_json(request):
            # HTML-by-design route — let Django render its normal page.
            return None

        logger.exception(
            "Unhandled exception in %s %s: %s",
            request.method,
            request.path,
            exception,
        )

        body: dict = {"detail": "Internal server error."}
        if settings.DEBUG:
            # Local dev only — show the underlying exception so a developer
            # can diagnose without grepping the log. NEVER returned in prod.
            body["error"] = str(exception) or repr(exception)
            body["error_type"] = type(exception).__name__

        return JsonResponse(body, status=500)
