"""Records logged while serving a request carry that request's details."""
import logging
import threading
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import override_settings
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APITestCase, APITransactionTestCase
from rest_framework.views import APIView

from apps.system_logs import handler as handler_module
from apps.system_logs.models import SystemLogEntry
from apps.system_logs.redaction import REDACTED

User = get_user_model()
logger = logging.getLogger("apps.example.context_tests")


class _WarnView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token=None):
        logger.warning("probe warning")
        return Response({"ok": True})


class _BrokenView(APIView):
    def get(self, request):
        raise RuntimeError("probe failure")


class _Rollback(Exception):
    pass


ROLLED_BACK_EMAIL = "rolled.back@example.com"


class _RollbackView(APIView):
    """Saves a user, logs an error, then rolls the transaction back."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            with transaction.atomic():
                User.objects.create_user(email=ROLLED_BACK_EMAIL, password="pass123")
                logger.error("logged inside a rolled-back transaction")
                raise _Rollback()
        except _Rollback:
            pass
        return Response({"ok": True})


urlpatterns = [
    path("probe/", _WarnView.as_view()),
    path("probe/broken/", _BrokenView.as_view()),
    path("probe/consent/<str:token>/", _WarnView.as_view()),
    path("probe/rollback/", _RollbackView.as_view()),
]


@override_settings(
    ROOT_URLCONF=__name__,
    SYSTEM_LOG_DB_ENABLED=True,
    SYSTEM_LOG_DISPATCH_SYNC=True,
    SYSTEM_LOG_DB_LEVEL="WARNING",
)
class RequestContextTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="logged.user@example.com", password="pass123")

    def _probe_entry(self):
        return SystemLogEntry.objects.get(message="probe warning")

    def test_user_authenticated_by_drf_is_recorded(self):
        # force_authenticate signs in at DRF's level only: Django's middleware
        # still sees an anonymous user, the case this has to get right.
        self.client.force_authenticate(user=self.user)

        self.client.get("/probe/")

        self.assertEqual(self._probe_entry().user_id, self.user.id)

    def test_user_signed_in_by_session_is_recorded(self):
        self.client.force_login(self.user)

        self.client.get("/probe/")

        self.assertEqual(self._probe_entry().user_id, self.user.id)

    def test_anonymous_request_records_no_user(self):
        self.client.get("/probe/")
        self.assertIsNone(self._probe_entry().user_id)

    def test_records_method_path_and_request_id(self):
        self.client.force_authenticate(user=self.user)

        self.client.get("/probe/?token=secret", HTTP_X_REQUEST_ID="trace-123")

        entry = self._probe_entry()
        self.assertEqual(entry.request_method, "GET")
        self.assertEqual(entry.request_path, "/probe/")  # no query string
        self.assertEqual(entry.request_id, "trace-123")

    def test_secret_path_arguments_are_redacted(self):
        self.client.get("/probe/consent/short-token/")
        self.assertEqual(self._probe_entry().request_path, f"/probe/consent/{REDACTED}/")

    def test_error_response_request_id_matches_the_logged_rows(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/probe/broken/")

        self.assertEqual(response.status_code, 500)
        request_id = response.data["request_id"]
        rows = SystemLogEntry.objects.filter(request_id=request_id)
        self.assertTrue(rows.exists())
        unhandled = rows.get(logger_name="config.exception_handler")
        self.assertIn("RuntimeError: probe failure", unhandled.traceback)
        self.assertEqual(unhandled.user_id, self.user.id)
        # Django's own record of the 500 carries the status code.
        self.assertTrue(rows.filter(logger_name="django.request", status_code=500).exists())

    def test_a_request_still_succeeds_when_the_log_table_is_unavailable(self):
        from django.db import DatabaseError

        with mock.patch.object(SystemLogEntry.objects, "create", side_effect=DatabaseError("no table")):
            response = self.client.get("/probe/")
        self.assertEqual(response.status_code, 200)


class _RealWriterMixin:
    """Runs a request with the real background writer, as in production,
    instead of the inline mode the other tests use.

    Inline writes go through the request's own connection, so a request that
    rolls back takes them with it; the writer saves on its own connection
    after the request. A TransactionTestCase makes real commits the writer's
    thread can see.
    """

    def send_with_writer(self, send):
        writer = handler_module._Writer()
        written = threading.Event()
        real_write = writer.write_batch

        def write_and_signal(batch, **kwargs):
            real_write(batch, **kwargs)
            written.set()

        writer.write_batch = write_and_signal
        # A short batching wait keeps the test quick; it still writes well
        # after the request's transaction has rolled back.
        with mock.patch.object(handler_module, "_writer", writer), \
                mock.patch.object(handler_module, "FLUSH_SECONDS", 0.5):
            response = send()
            self.assertTrue(written.wait(10), "the writer never saved the batch")
        return response


REAL_WRITER = override_settings(SYSTEM_LOG_DB_ENABLED=True, SYSTEM_LOG_DISPATCH_SYNC=False, SYSTEM_LOG_DB_LEVEL="WARNING")


@REAL_WRITER
@override_settings(ROOT_URLCONF=__name__)
class RolledBackTransactionTests(_RealWriterMixin, APITransactionTestCase):
    def test_log_row_survives_the_rollback_of_the_request_transaction(self):
        response = self.send_with_writer(lambda: self.client.post("/probe/rollback/"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email=ROLLED_BACK_EMAIL).exists())
        entry = SystemLogEntry.objects.get(message="logged inside a rolled-back transaction")
        self.assertEqual(entry.level_name, "ERROR")
        self.assertEqual(entry.request_path, "/probe/rollback/")


@REAL_WRITER
class RealViewWarningTests(_RealWriterMixin, APITransactionTestCase):
    def test_blocked_self_profile_change_logs_a_warning_with_the_user(self):
        # The warning to trigger by hand: PATCH /api/v1/users/me/ with an
        # admin-only field. It's refused (400) and nothing changes. The view
        # is @transaction.atomic, so the 400 also rolls back: a real case of
        # the row having to outlive the request's transaction.
        user = User.objects.create_user(email="warns@example.com", password="pass123")
        self.client.force_login(user)

        response = self.send_with_writer(
            lambda: self.client.patch("/api/v1/users/me/", {"is_staff": True}, format="json")
        )

        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        entry = SystemLogEntry.objects.get(logger_name="apps.users.views")
        self.assertEqual(entry.level_name, "WARNING")
        self.assertIn("attempted to mutate admin-only fields=['is_staff']", entry.message)
        self.assertEqual(entry.user_id, user.id)
        self.assertEqual((entry.request_method, entry.request_path), ("PATCH", "/api/v1/users/me/"))
        self.assertIsNone(entry.status_code)  # logged mid-view, before the response exists
