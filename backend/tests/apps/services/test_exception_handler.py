"""Tests for the unified DRF exception handler.

Goal: every exception raised inside a DRF view comes out as JSON, not HTML.
The frontend should never receive Django's yellow debug page or a generic 500
HTML response.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework import exceptions as drf_exceptions, status

from apps.services.exception_handler import (
    _normalise_payload,
    unified_exception_handler,
)


def _ctx(view_class_name: str = "FakeView") -> dict:
    """Minimal DRF exception_handler context — handler only looks at ``view``."""
    view = MagicMock()
    view.__class__.__name__ = view_class_name
    return {"view": view, "request": RequestFactory().get("/")}


class NormalisePayloadTests(unittest.TestCase):
    def test_dict_passes_through(self):
        self.assertEqual(_normalise_payload({"detail": "x"}), {"detail": "x"})

    def test_list_is_wrapped_in_detail(self):
        self.assertEqual(_normalise_payload(["a", "b"]), {"detail": ["a", "b"]})

    def test_string_is_wrapped_in_detail(self):
        self.assertEqual(_normalise_payload("oops"), {"detail": "oops"})


class HandledExceptionTests(SimpleTestCase):
    """DRF already knows how to convert these — we just normalise the body."""

    def test_not_authenticated_returns_401_json(self):
        response = unified_exception_handler(
            drf_exceptions.NotAuthenticated(),
            _ctx(),
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIsInstance(response.data, dict)
        self.assertIn("detail", response.data)

    def test_permission_denied_returns_403_json(self):
        response = unified_exception_handler(
            drf_exceptions.PermissionDenied("nope"),
            _ctx(),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {"detail": "nope"})

    def test_drf_validation_error_returns_400_json(self):
        response = unified_exception_handler(
            drf_exceptions.ValidationError(["field is required"]),
            _ctx(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF returns a list for unkeyed validation errors; we wrap to a dict
        # so the frontend always reads ``response.detail``.
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data, {"detail": ["field is required"]})


class DjangoValidationErrorTests(SimpleTestCase):
    """Django's own ValidationError isn't an APIException — handle it explicitly."""

    def test_django_validation_error_returns_400_json(self):
        response = unified_exception_handler(
            DjangoValidationError("bad data"),
            _ctx(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Validation error.")
        self.assertEqual(response.data["messages"], ["bad data"])


class UnhandledExceptionTests(SimpleTestCase):
    """The whole point of the new handler: ``ValueError``, ``KeyError``, etc.
    used to fall through and become Django's HTML 500/debug page. They must
    now come back as JSON 500."""

    @override_settings(DEBUG=True)
    def test_value_error_returns_500_json_with_debug_info(self):
        response = unified_exception_handler(
            ValueError("The annotation 'user_id' conflicts with a field on the model."),
            _ctx(view_class_name="MentorListView"),
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "Internal server error.")
        # DEBUG=True: include the underlying exception so devs can diagnose
        # without checking the server log.
        self.assertEqual(
            response.data["error"],
            "The annotation 'user_id' conflicts with a field on the model.",
        )
        self.assertEqual(response.data["error_type"], "ValueError")

    @override_settings(DEBUG=False)
    def test_value_error_returns_minimal_json_in_production(self):
        response = unified_exception_handler(
            ValueError("internal db secret leaked here"),
            _ctx(),
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Production: never leak the raw exception to the API consumer.
        self.assertEqual(response.data, {"detail": "Internal server error."})
        self.assertNotIn("error", response.data)
        self.assertNotIn("error_type", response.data)

    @override_settings(DEBUG=False)
    def test_arbitrary_exception_classes_are_all_caught(self):
        # Belt-and-braces: anything that subclasses ``Exception`` should be
        # converted to JSON, regardless of type.
        for exc in (
            KeyError("missing"),
            TypeError("wrong type"),
            RuntimeError("kaboom"),
            ZeroDivisionError("integer division by zero"),
        ):
            with self.subTest(exc=type(exc).__name__):
                response = unified_exception_handler(exc, _ctx())
                self.assertEqual(
                    response.status_code,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
                self.assertIsInstance(response.data, dict)
                self.assertEqual(response.data["detail"], "Internal server error.")

    @override_settings(DEBUG=True)
    def test_unhandled_exception_logs_traceback(self):
        with self.assertLogs(
            "apps.services.exception_handler", level="ERROR"
        ) as captured:
            unified_exception_handler(
                ValueError("boom"),
                _ctx(view_class_name="MentorListView"),
            )
        # The view name must appear in the log so the on-call engineer knows
        # which endpoint blew up.
        self.assertTrue(
            any("MentorListView" in line for line in captured.output),
            f"View name not logged. Got: {captured.output}",
        )
