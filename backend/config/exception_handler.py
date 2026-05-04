from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc: Exception, context: dict) -> Response:
    response = drf_exception_handler(exc, context)
    if response is None:
        return _build_unhandled_error_response()
    return _reshape_drf_response(response)


def _build_unhandled_error_response() -> Response:
    return Response(
        {"error": "Internal server error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _reshape_drf_response(response: Response) -> Response:
    payload: dict[str, Any] = {"error": _extract_message(response.data)}
    field_errors = _extract_field_errors(response.data)
    if field_errors:
        payload["fields"] = field_errors
    response.data = payload
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


def _extract_field_errors(data: Any) -> Optional[dict]:
    if not isinstance(data, dict):
        return None
    fields = {key: value for key, value in data.items() if key != "detail"}
    return fields or None