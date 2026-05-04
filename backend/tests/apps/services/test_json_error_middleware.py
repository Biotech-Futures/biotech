"""Tests for ``JsonErrorMiddleware``.

The DRF exception handler covers anything that goes through DRF's dispatch.
This middleware is the safety net for everything else — plain Django views,
exceptions raised before DRF dispatch, exceptions raised by the DRF handler
itself. We test both behaviours: convert to JSON for API paths, and leave
the HTML-by-design routes alone.
"""

from __future__ import annotations

import json

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.services.json_error_middleware import (
    HTML_RESPONSE_PREFIXES,
    JsonErrorMiddleware,
    _wants_json,
)


def _identity_get_response(request):
    # Stand-in ``get_response`` callable; never invoked because
    # ``process_exception`` is called directly in these tests.
    raise AssertionError("get_response should not run during these tests")


class WantsJsonTests(SimpleTestCase):
    """Path allowlist sanity check — the contract of which routes stay HTML."""

    def setUp(self):
        self.rf = RequestFactory()

    def test_api_paths_want_json(self):
        for path in (
            "/api/v1/users/",
            "/chat/groups/135/messages/",
            "/services/send-login-code/",
            "/dashboard/v1/stats/",
            "/events/",
            "/groups/",
            "/tasks/",
            "/resources/",
            "/some/totally/new/api/path/",
        ):
            with self.subTest(path=path):
                request = self.rf.get(path)
                self.assertTrue(_wants_json(request))

    def test_html_routes_do_not_want_json(self):
        for prefix in HTML_RESPONSE_PREFIXES:
            with self.subTest(prefix=prefix):
                request = self.rf.get(prefix + "anything")
                self.assertFalse(_wants_json(request))


class ProcessExceptionTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.middleware = JsonErrorMiddleware(_identity_get_response)

    @override_settings(DEBUG=True)
    def test_api_path_returns_json_500_with_debug_info(self):
        request = self.rf.get("/api/v1/admin/mentor/")
        response = self.middleware.process_exception(
            request,
            ValueError("The annotation 'user_id' conflicts with a field on the model."),
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["Content-Type"], "application/json")
        body = json.loads(response.content)
        self.assertEqual(body["detail"], "Internal server error.")
        self.assertEqual(
            body["error"],
            "The annotation 'user_id' conflicts with a field on the model.",
        )
        self.assertEqual(body["error_type"], "ValueError")

    @override_settings(DEBUG=False)
    def test_api_path_returns_minimal_json_in_production(self):
        request = self.rf.get("/api/v1/users/")
        response = self.middleware.process_exception(
            request, RuntimeError("internal db secret leaked here")
        )
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content)
        # Production must not leak the raw exception to the API consumer.
        self.assertEqual(body, {"detail": "Internal server error."})
        self.assertNotIn("error", body)
        self.assertNotIn("error_type", body)

    def test_admin_path_falls_through_to_django_html(self):
        # Returning ``None`` from process_exception lets Django render its
        # native HTML response (yellow page in DEBUG, generic 500 in prod).
        # We rely on this so the Django admin keeps working.
        request = self.rf.get("/admin/users/")
        response = self.middleware.process_exception(request, ValueError("x"))
        self.assertIsNone(response)

    def test_swagger_docs_falls_through_to_django_html(self):
        request = self.rf.get("/api/docs/")
        self.assertIsNone(
            self.middleware.process_exception(request, ValueError("x"))
        )

    def test_static_path_falls_through_to_django_html(self):
        request = self.rf.get("/static/css/app.css")
        self.assertIsNone(
            self.middleware.process_exception(request, ValueError("x"))
        )

    @override_settings(DEBUG=True)
    def test_arbitrary_exception_classes_are_caught(self):
        request = self.rf.get("/services/anything/")
        for exc in (
            KeyError("missing"),
            TypeError("nope"),
            RuntimeError("kaboom"),
            ZeroDivisionError("integer division by zero"),
        ):
            with self.subTest(exc=type(exc).__name__):
                response = self.middleware.process_exception(request, exc)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response["Content-Type"], "application/json")
                body = json.loads(response.content)
                self.assertEqual(body["detail"], "Internal server error.")

    @override_settings(DEBUG=True)
    def test_unhandled_exception_logs_method_path_and_exception(self):
        request = self.rf.post("/chat/groups/135/messages/")
        with self.assertLogs(
            "apps.services.json_error_middleware", level="ERROR"
        ) as captured:
            self.middleware.process_exception(request, ValueError("boom"))
        log_text = "\n".join(captured.output)
        self.assertIn("POST", log_text)
        self.assertIn("/chat/groups/135/messages/", log_text)
