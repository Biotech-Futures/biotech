"""
Tests for announcement email delivery tracking.

Background
----------
The previous implementation in ``apps.admin.services.announcement`` called
``send_mail(..., fail_silently=True)`` and then returned a constant
``"Email sent successfully"`` response regardless of whether anything actually
left the SMTP server. There was no audit trail for which recipients bounced.

This module covers the engagement-aware replacement:

  * ``fail_silently`` is **never** passed as True anywhere in the path.
  * Every send attempt persists an :class:`AnnouncementDelivery` row.
  * Success / partial-success / total-failure paths each produce the correct
    status, counters, and HTTP response code.
  * The legacy ``"sent"`` key is preserved for backward compatibility.
"""

from unittest.mock import patch, MagicMock

from django.core.mail import get_connection as _real_get_connection
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.announcement import send_announcement_email
from apps.announcements.models import Announcement, AnnouncementDelivery
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AnnouncementEmailDeliveryServiceTests(TestCase):
    """Service-layer tests for ``send_announcement_email``."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="author@example.com",
            password="testpass",
            first_name="An",
            last_name="Author",
        )
        # Two real recipients so partial-failure can be exercised.
        self.r1 = User.objects.create_user(
            email="r1@example.com",
            password="testpass",
            first_name="Recip",
            last_name="One",
        )
        self.r2 = User.objects.create_user(
            email="r2@example.com",
            password="testpass",
            first_name="Recip",
            last_name="Two",
        )
        self.announcement = Announcement.objects.create(
            author_user=self.author,
            title="Hello",
            body="<p>This is the body.</p>",
            visibility_scope="global",
        )

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_successful_send_records_delivery_and_clears_failures(self):
        result = send_announcement_email(self.announcement.id, initiated_by=self.author)

        self.assertEqual(result["status"], AnnouncementDelivery.Status.SUCCESS)
        self.assertGreaterEqual(result["attempted"], 1)
        self.assertEqual(result["succeeded"], result["attempted"])
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["failedRecipients"], [])
        # Legacy alias preserved.
        self.assertEqual(result["sent"], result["succeeded"])

        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertEqual(delivery.announcement_id, self.announcement.id)
        self.assertEqual(delivery.initiated_by, self.author)
        self.assertEqual(delivery.status, AnnouncementDelivery.Status.SUCCESS)
        self.assertEqual(delivery.success_count, result["attempted"])
        self.assertEqual(delivery.failure_count, 0)
        self.assertEqual(delivery.failed_recipients, [])
        self.assertEqual(delivery.error_summary, "")
        self.assertIsNotNone(delivery.completed_at)

    # ------------------------------------------------------------------
    # All-fail path: mail backend rejects every recipient.
    # ------------------------------------------------------------------
    def test_all_recipients_failing_records_failed_delivery(self):
        with patch(
            "apps.admin.services.announcement.EmailMultiAlternatives.send",
            side_effect=Exception("smtp down"),
        ):
            result = send_announcement_email(self.announcement.id)

        self.assertEqual(result["status"], AnnouncementDelivery.Status.FAILED)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["failed"], result["attempted"])
        self.assertEqual(len(result["failedRecipients"]), result["attempted"])

        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertEqual(delivery.status, AnnouncementDelivery.Status.FAILED)
        self.assertEqual(delivery.success_count, 0)
        self.assertEqual(delivery.failure_count, result["attempted"])
        # Each failed entry carries an error string.
        for entry in delivery.failed_recipients:
            self.assertIn("smtp down", entry["error"])

    # ------------------------------------------------------------------
    # Mixed: first recipient succeeds, rest fail.
    # ------------------------------------------------------------------
    def test_partial_failure_records_mixed_status(self):
        call_count = {"n": 0}

        def fake_send(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return 1  # first one succeeds
            raise Exception("recipient rejected")

        with patch(
            "apps.admin.services.announcement.EmailMultiAlternatives.send",
            new=fake_send,
        ):
            result = send_announcement_email(self.announcement.id)

        # We have 3 active users (author + 2 recipients), so attempted >= 2.
        self.assertGreaterEqual(result["attempted"], 2)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], result["attempted"] - 1)
        self.assertEqual(result["status"], AnnouncementDelivery.Status.PARTIAL)

        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertEqual(delivery.status, AnnouncementDelivery.Status.PARTIAL)
        self.assertEqual(delivery.success_count, 1)
        self.assertEqual(delivery.failure_count, result["failed"])
        self.assertGreaterEqual(len(delivery.failed_recipients), 1)

    # ------------------------------------------------------------------
    # SMTP connection itself can't even open: every recipient marked failed
    # and an error summary captures the connection cause.
    # ------------------------------------------------------------------
    def test_connection_open_failure_marks_all_failed_with_summary(self):
        bad_connection = MagicMock()
        bad_connection.open.side_effect = Exception("network unreachable")

        with patch(
            "apps.admin.services.announcement.get_connection",
            return_value=bad_connection,
        ):
            result = send_announcement_email(self.announcement.id)

        self.assertEqual(result["status"], AnnouncementDelivery.Status.FAILED)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["failed"], result["attempted"])

        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertIn("network unreachable", delivery.error_summary)

    # ------------------------------------------------------------------
    # No recipients: skip cleanly, do NOT persist a delivery row.
    # ------------------------------------------------------------------
    def test_no_recipients_skipped_and_no_delivery_row(self):
        # Deactivate every user so _resolve_recipient_emails returns [].
        User.objects.update(is_active=False)

        result = send_announcement_email(self.announcement.id)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["attempted"], 0)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertIsNone(result["deliveryId"])
        self.assertFalse(
            AnnouncementDelivery.objects.filter(
                announcement_id=self.announcement.id,
            ).exists()
        )

    # ------------------------------------------------------------------
    # Unknown announcement id: short-circuit, don't persist.
    # ------------------------------------------------------------------
    def test_unknown_announcement_returns_skipped(self):
        result = send_announcement_email(999_999)
        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["deliveryId"])
        self.assertFalse(AnnouncementDelivery.objects.exists())

    # ------------------------------------------------------------------
    # Persisted error strings must be sanitized: prefixed with the
    # exception class name, length-bounded, and CR/LF-stripped so a
    # malicious SMTP banner can't smuggle log lines or leak details.
    # ------------------------------------------------------------------
    def test_failed_recipient_errors_are_sanitized(self):
        nasty = (
            "550 5.1.1 <user@example.com>: rejected\r\n"
            "X-Internal-Hostname: smtp-internal.corp.example.com\n"
            + "A" * 500
        )
        with patch(
            "apps.admin.services.announcement.EmailMultiAlternatives.send",
            side_effect=Exception(nasty),
        ):
            result = send_announcement_email(self.announcement.id)

        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertGreaterEqual(len(delivery.failed_recipients), 1)
        for entry in delivery.failed_recipients:
            err = entry["error"]
            self.assertTrue(
                err.startswith("Exception: "),
                f"missing class-name prefix in {err!r}",
            )
            self.assertNotIn("\n", err)
            self.assertNotIn("\r", err)
            # Class prefix ("Exception: ") + truncated message + ellipsis.
            self.assertLess(len(err), 260)

    # ------------------------------------------------------------------
    # The inner ``finally`` swallows connection-close errors but still
    # logs them. Make sure the outer call still reports success and the
    # delivery row is still persisted.
    # ------------------------------------------------------------------
    def test_connection_close_failure_is_swallowed(self):
        real_conn = _real_get_connection()

        class FlakyConnection:
            """Wraps a real connection but explodes on ``close()``."""

            def __init__(self, inner):
                self._inner = inner

            def open(self):
                return self._inner.open()

            def send_messages(self, messages):
                return self._inner.send_messages(messages)

            def close(self):
                raise RuntimeError("simulated close failure")

        with patch(
            "apps.admin.services.announcement.get_connection",
            return_value=FlakyConnection(real_conn),
        ):
            result = send_announcement_email(self.announcement.id)

        # The send still counts as successful — close errors don't
        # invalidate already-accepted messages.
        self.assertEqual(result["status"], AnnouncementDelivery.Status.SUCCESS)
        self.assertGreaterEqual(result["succeeded"], 1)
        # And the delivery row is still saved.
        self.assertTrue(
            AnnouncementDelivery.objects.filter(pk=result["deliveryId"]).exists()
        )

    # ------------------------------------------------------------------
    # Regression guard: nothing in the path may opt back into the silent
    # mode. We assert the connection is opened with fail_silently=False.
    # ------------------------------------------------------------------
    def test_uses_non_silent_smtp_connection(self):
        with patch(
            "apps.admin.services.announcement.get_connection",
            wraps=_real_get_connection,
        ) as spy:
            send_announcement_email(self.announcement.id)

        self.assertTrue(spy.called)
        # Every invocation must explicitly disable fail_silently.
        for call in spy.call_args_list:
            self.assertFalse(call.kwargs.get("fail_silently", False))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AnnouncementNotifyViewTests(TestCase):
    """HTTP-layer tests for ``AnnouncementNotifyView``."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            first_name="Admin",
            last_name="User",
        )
        AdminScope.objects.create(user=self.admin, is_global=True)

        self.recipient = User.objects.create_user(
            email="recip@example.com",
            password="testpass",
            first_name="Recip",
            last_name="One",
        )
        self.announcement = Announcement.objects.create(
            author_user=self.admin,
            title="Hi",
            body="<p>body</p>",
            visibility_scope="global",
        )

        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        # ``reverse`` is unreliable here because the project mounts two
        # ``admin/`` namespaces (Django's built-in admin and our REST app),
        # which collide. The path is stable enough to hard-code in tests.
        self.url = f"/api/v1/admin/announcement/{self.announcement.id}/notify/"

    def test_successful_notify_returns_200_with_rich_body(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertGreaterEqual(body["succeeded"], 1)
        self.assertEqual(body["failed"], 0)
        self.assertEqual(body["failedRecipients"], [])
        # Legacy alias still present.
        self.assertEqual(body["sent"], body["succeeded"])
        self.assertIsNotNone(body["deliveryId"])

    def test_all_failed_notify_returns_502(self):
        with patch(
            "apps.admin.services.announcement.EmailMultiAlternatives.send",
            side_effect=Exception("smtp dead"),
        ):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["succeeded"], 0)
        self.assertGreaterEqual(body["failed"], 1)
        # Legacy alias parity — succeeded/sent must agree on every path.
        self.assertEqual(body["sent"], 0)

    def test_partial_failure_returns_207(self):
        call_count = {"n": 0}

        def fake_send(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return 1
            raise Exception("rejected")

        with patch(
            "apps.admin.services.announcement.EmailMultiAlternatives.send",
            new=fake_send,
        ):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        body = response.json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["succeeded"], 1)
        self.assertGreaterEqual(body["failed"], 1)

    def test_no_recipients_returns_400(self):
        # Deactivate every non-admin so the global-scope audience is empty.
        # We deliberately leave the admin active so the authenticated request
        # still passes IsAdminScoped — the response should still be 400 because
        # an audience of one (just the admin) is fine; we want a *true* empty
        # audience, so target a track that has no users.
        from apps.groups.models import Countries, CountryStates, Tracks
        country = Countries.objects.create(country_name="C")
        state = CountryStates.objects.create(country=country, state_name="S")
        empty_track = Tracks.objects.create(track_name="EMPTY", state=state)
        # Re-target the announcement to a track with zero active users.
        from apps.announcements.models import AnnouncementAudience
        AnnouncementAudience.objects.create(
            announcement=self.announcement, track=empty_track,
        )
        self.announcement.visibility_scope = "track_based"
        self.announcement.save(update_fields=["visibility_scope"])

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.json()
        self.assertEqual(body["status"], "skipped")

    def test_unknown_announcement_returns_400(self):
        url = "/api/v1/admin/announcement/999999/notify/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.json()
        self.assertEqual(body["status"], "skipped")

    def test_notify_records_initiator_on_delivery_row(self):
        self.client.post(self.url)
        delivery = AnnouncementDelivery.objects.filter(
            announcement_id=self.announcement.id,
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.initiated_by, self.admin)
