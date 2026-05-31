import logging
import uuid
from typing import Any, Optional

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def custom_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    request_id = _resolve_request_id(context)
    response = drf_exception_handler(exc, context)
    if response is None:
        return _build_unhandled_error_response(exc, context, request_id)
    return _reshape_drf_response(response, exc, request_id)


def _resolve_request_id(context: dict) -> str:
    request = context.get("request")
    if request is not None:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        if incoming:
            return incoming
    return uuid.uuid4().hex[:12]


def _build_unhandled_error_response(exc: Exception, context: dict, request_id: str) -> Response:
    view = context.get("view")
    view_name = view.__class__.__name__ if view else "unknown_view"
    logger.exception(
        "Unhandled exception in %s [request_id=%s]",
        view_name,
        request_id,
    )
    payload: dict[str, Any] = {
        "error": "Internal server error",
        "code": "internal_server_error",
        "request_id": request_id,
    }
    if settings.DEBUG:
        payload["detail"] = str(exc)
        payload["exception_type"] = type(exc).__name__
    response = Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    response[REQUEST_ID_HEADER] = request_id
    return response


def _reshape_drf_response(response: Response, exc: Exception, request_id: str) -> Response:
    payload: dict[str, Any] = {
        "error": _extract_message(response.data),
        "request_id": request_id,
    }
    code = _extract_code(response.data) or getattr(exc, "default_code", None)
    if code:
        payload["code"] = code
    field_errors = _extract_field_errors(response.data)
    if field_errors:
        payload["fields"] = field_errors
    extra = getattr(exc, "extra", None)
    if isinstance(extra, dict):
        payload.update(extra)
    response.data = payload
    response[REQUEST_ID_HEADER] = request_id
    logger.info(
        "Handled %s -> %d [request_id=%s]",
        type(exc).__name__,
        response.status_code,
        request_id,
    )
    return response


def _extract_message(data: Any) -> str:
    if isinstance(data, str):
        return str(data)
    if isinstance(data, list):
        return _extract_message(data[0]) if data else "Error"
    if isinstance(data, dict):
        if "detail" in data:
            return _extract_message(data["detail"])
        for value in data.values():
            return _extract_message(value)
    return str(data) if data is not None else "Error"


def _extract_code(data: Any) -> Optional[str]:
    if isinstance(data, str):
        return getattr(data, "code", None)
    if isinstance(data, list):
        return _extract_code(data[0]) if data else None
    if isinstance(data, dict):
        if "detail" in data:
            return _extract_code(data["detail"])
        for value in data.values():
            return _extract_code(value)
    return None


def _extract_field_errors(data: Any) -> Optional[dict]:
    if not isinstance(data, dict):
        return None
    fields = {key: value for key, value in data.items() if key != "detail"}
    return fields or None