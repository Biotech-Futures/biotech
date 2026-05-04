"""Unified DRF exception handler — every exception leaves the API as JSON.

Why this exists
---------------
By default, DRF's ``rest_framework.views.exception_handler`` only converts
``APIException`` subclasses, ``Http404``, and ``PermissionDenied`` into JSON
responses. Anything else — ``ValueError``, ``KeyError``, ``IntegrityError``,
``django.core.exceptions.ValidationError``, etc. — falls through and Django
renders the yellow HTML debug page (with ``DEBUG=True``) or a generic HTML
500 page (in production). Either way, a single-page frontend cannot parse
the body and has no way to surface the error to the user.

This handler guarantees that EVERY exception raised in a DRF view is returned
as a JSON object the frontend can render uniformly:

    { "detail": "<human-readable message>" }

In ``DEBUG`` mode (i.e. local dev) the response also includes ``error`` and
``error_type`` so a developer can diagnose without checking the server log.
Production responses stay minimal so we don't leak internals.

Wiring
------
Set ``REST_FRAMEWORK['EXCEPTION_HANDLER']`` to
``"apps.services.exception_handler.unified_exception_handler"`` in
``config/settings.py``. The default handler is a drop-in fallback for known
DRF exceptions; we wrap it for the unknown ones.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

logger = logging.getLogger(__name__)


def _normalise_payload(data) -> dict:
    """Force a dict shape so the frontend can rely on ``response.detail``.

    DRF's default handler sometimes returns a list (validation errors with no
    field name) or a bare string. The frontend should not have to type-check
    every error response — coerce to ``{"detail": <thing>}``.
    """
    if isinstance(data, dict):
        return data
    return {"detail": data}


def unified_exception_handler(exc, context):
    """DRF-compatible handler that always returns a JSON ``Response``.

    Order of precedence:

    1. DRF can handle it (``APIException``, ``Http404``, ``PermissionDenied``)
       → use DRF's response, normalised to a dict body.
    2. It's a Django ``ValidationError`` → 400 with ``messages``.
    3. Anything else → 500 with ``detail`` (+ debug info when ``DEBUG``).

    Side effect: unhandled exceptions are logged at ERROR level with full
    traceback. Without this we would silently swallow server bugs.
    """
    response = drf_default_handler(exc, context)

    if response is not None:
        response.data = _normalise_payload(response.data)
        return response

    # Django's own ValidationError isn't an APIException, so DRF skips it.
    # Map it to 400 because it is, semantically, a client validation failure.
    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": "Validation error.", "messages": exc.messages},
            status=status.HTTP_400_BAD_REQUEST,
        )

    view = context.get("view")
    view_name = view.__class__.__name__ if view is not None else "<unknown view>"
    logger.exception("Unhandled exception in %s: %s", view_name, exc)

    body: dict = {"detail": "Internal server error."}
    if settings.DEBUG:
        # Local dev only — give the developer the actual exception message and
        # type without needing to read the server log. NEVER returned in prod.
        body["error"] = str(exc) or repr(exc)
        body["error_type"] = type(exc).__name__
    return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
