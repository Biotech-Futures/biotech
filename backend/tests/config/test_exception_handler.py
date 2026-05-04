from unittest.mock import MagicMock

from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import ErrorDetail, NotAuthenticated, ValidationError

from config.exception_handler import (
    REQUEST_ID_HEADER,
    _build_unhandled_error_response,
    _extract_code,
    _extract_field_errors,
    _extract_message,
    _reshape_drf_response,
    _resolve_request_id,
    custom_exception_handler,
)


def _make_view(name: str = "TestView") -> MagicMock:
    view_cls = type(name, (), {})
    return MagicMock(__class__=view_cls)


class ExtractMessageTests(SimpleTestCase):
    def test_string_passthrough(self):
        self.assertEqual(_extract_message("hello"), "hello")

    def test_list_picks_first(self):
        self.assertEqual(_extract_message(["first", "second"]), "first")

    def test_empty_list_default(self):
        self.assertEqual(_extract_message([]), "Error")

    def test_dict_with_detail(self):
        self.assertEqual(_extract_message({"detail": "auth required"}), "auth required")

    def test_dict_validation(self):
        data = {"email": ["This field is required."]}
        self.assertEqual(_extract_message(data), "This field is required.")

    def test_nested_dict_in_list(self):
        data = {"items": [{"name": ["bad"]}]}
        self.assertEqual(_extract_message(data), "bad")

    def test_none_default(self):
        self.assertEqual(_extract_message(None), "Error")


class ExtractCodeTests(SimpleTestCase):
    def test_error_detail_returns_code(self):
        ed = ErrorDetail("msg", code="my_code")
        self.assertEqual(_extract_code(ed), "my_code")

    def test_plain_str_returns_none(self):
        self.assertIsNone(_extract_code("plain string"))

    def test_dict_with_error_detail_under_detail(self):
        ed = ErrorDetail("auth", code="not_authenticated")
        self.assertEqual(_extract_code({"detail": ed}), "not_authenticated")

    def test_dict_validation_first_field(self):
        data = {"email": [ErrorDetail("required", code="required")]}
        self.assertEqual(_extract_code(data), "required")

    def test_list_empty_returns_none(self):
        self.assertIsNone(_extract_code([]))

    def test_no_code_anywhere_returns_none(self):
        self.assertIsNone(_extract_code({"email": ["plain str"]}))


class ExtractFieldErrorsTests(SimpleTestCase):
    def test_only_detail_returns_none(self):
        self.assertIsNone(_extract_field_errors({"detail": "x"}))

    def test_field_errors_preserved(self):
        data = {"email": ["err1"], "password": ["err2"]}
        self.assertEqual(_extract_field_errors(data), data)

    def test_strips_detail_keeps_other_fields(self):
        result = _extract_field_errors({"detail": "x", "email": ["err"]})
        self.assertEqual(result, {"email": ["err"]})

    def test_non_dict_returns_none(self):
        self.assertIsNone(_extract_field_errors("x"))
        self.assertIsNone(_extract_field_errors(["x"]))
        self.assertIsNone(_extract_field_errors(None))


class ResolveRequestIdTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_inherits_incoming_header(self):
        request = self.factory.get("/", HTTP_X_REQUEST_ID="trace-abc-123")
        self.assertEqual(
            _resolve_request_id({"request": request}),
            "trace-abc-123",
        )

    def test_generates_when_missing_header(self):
        request = self.factory.get("/")
        rid = _resolve_request_id({"request": request})
        self.assertEqual(len(rid), 12)
        int(rid, 16)  # must be valid hex

    def test_generates_when_no_request_in_context(self):
        rid = _resolve_request_id({})
        self.assertEqual(len(rid), 12)
        int(rid, 16)

    def test_generated_ids_unique(self):
        rid1 = _resolve_request_id({})
        rid2 = _resolve_request_id({})
        self.assertNotEqual(rid1, rid2)


class BuildUnhandledTests(SimpleTestCase):
    def test_shape_status_and_header(self):
        ctx = {"view": _make_view("FooView")}
        response = _build_unhandled_error_response(ValueError("boom"), ctx, "rid_abc123")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"], "Internal server error")
        self.assertEqual(response.data["code"], "internal_server_error")
        self.assertEqual(response.data["request_id"], "rid_abc123")
        self.assertEqual(response[REQUEST_ID_HEADER], "rid_abc123")

    def test_handles_missing_view(self):
        response = _build_unhandled_error_response(ValueError("x"), {}, "rid")
        self.assertEqual(response.status_code, 500)


class ReshapeResponseTests(SimpleTestCase):
    def _drf_like_response(self, data, status_code=400):
        from rest_framework.response import Response
        return Response(data, status=status_code)

    def test_reshapes_with_code_and_request_id(self):
        ed = ErrorDetail("Email required", code="required")
        response = self._drf_like_response({"email": [ed]})
        reshaped = _reshape_drf_response(response, Exception(), "rid_xyz")

        self.assertEqual(reshaped.data["error"], "Email required")
        self.assertEqual(reshaped.data["code"], "required")
        self.assertEqual(reshaped.data["request_id"], "rid_xyz")
        self.assertEqual(reshaped.data["fields"], {"email": [ed]})
        self.assertEqual(reshaped[REQUEST_ID_HEADER], "rid_xyz")

    def test_no_code_when_plain_strings(self):
        response = self._drf_like_response({"detail": "Plain string"})
        reshaped = _reshape_drf_response(response, Exception(), "rid")

        self.assertEqual(reshaped.data["error"], "Plain string")
        self.assertNotIn("code", reshaped.data)

    def test_no_fields_when_only_detail(self):
        response = self._drf_like_response({"detail": "x"})
        reshaped = _reshape_drf_response(response, Exception(), "rid")
        self.assertNotIn("fields", reshaped.data)

    def test_preserves_status_code(self):
        response = self._drf_like_response({"detail": "x"}, status_code=403)
        reshaped = _reshape_drf_response(response, Exception(), "rid")
        self.assertEqual(reshaped.status_code, 403)


class CustomExceptionHandlerEndToEndTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _ctx(self, view_name="TestView", incoming_rid=None):
        request_kwargs = {}
        if incoming_rid:
            request_kwargs["HTTP_X_REQUEST_ID"] = incoming_rid
        request = self.factory.get("/", **request_kwargs)
        return {"request": request, "view": _make_view(view_name)}

    def test_not_authenticated_returns_401_with_code(self):
        response = custom_exception_handler(NotAuthenticated(), self._ctx())

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "not_authenticated")
        self.assertIn("error", response.data)
        self.assertIn("request_id", response.data)
        self.assertIn(REQUEST_ID_HEADER, response)

    def test_validation_error_includes_fields(self):
        response = custom_exception_handler(
            ValidationError({"email": ["Required"]}),
            self._ctx(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Required")
        self.assertIn("fields", response.data)
        self.assertEqual(response.data["fields"]["email"], ["Required"])

    def test_unhandled_exception_returns_500(self):
        response = custom_exception_handler(ValueError("kaboom"), self._ctx())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"], "Internal server error")
        self.assertEqual(response.data["code"], "internal_server_error")
        self.assertIn("request_id", response.data)

    def test_inherits_incoming_request_id(self):
        response = custom_exception_handler(
            NotAuthenticated(),
            self._ctx(incoming_rid="trace-from-fe"),
        )

        self.assertEqual(response.data["request_id"], "trace-from-fe")
        self.assertEqual(response[REQUEST_ID_HEADER], "trace-from-fe")

    def test_inherits_request_id_on_unhandled(self):
        response = custom_exception_handler(
            ValueError("boom"),
            self._ctx(incoming_rid="trace-500"),
        )

        self.assertEqual(response.data["request_id"], "trace-500")
        self.assertEqual(response[REQUEST_ID_HEADER], "trace-500")