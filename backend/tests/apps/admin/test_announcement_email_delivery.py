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
from django.db import transaction
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.announcement import (
    create_announcement,
    send_announcement_email,
    update_announcement,
)
from apps.announcements.models import (
    Announcement,
    AnnouncementAudience,
    AnnouncementDelivery,
)
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
    #
    # We target the announcement at an audience that resolves to zero
    # users (an empty group) rather than flipping every ``User`` to
    # inactive — that approach in earlier revisions deactivated the
    # author itself and accidentally exercised the auth/admin model.
    # The empty-group path is the same one ``test_no_recipients_returns_400``
    # uses for the HTTP layer.
    # ------------------------------------------------------------------
    def test_no_recipients_skipped_and_no_delivery_row(self):
        from apps.groups.models import Groups
        empty_group = Groups.objects.create(group_name="SERVICE_EMPTY")
        AnnouncementAudience.objects.create(
            announcement=self.announcement, group=empty_group,
        )
        self.announcement.visibility_scope = "role_based"
        self.announcement.save(update_fields=["visibility_scope"])

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
        AdminScope.objects.create(user=self.admin)

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
        # We want a *true* empty audience: the admin stays active so the
        # authenticated request still passes IsAdminScoped, but we target a
        # group that has no members, so the resolved recipient set is empty.
        from apps.groups.models import Groups
        empty_group = Groups.objects.create(group_name="EMPTY")
        # Re-target the announcement to a group with zero active members.
        from apps.announcements.models import AnnouncementAudience
        AnnouncementAudience.objects.create(
            announcement=self.announcement, group=empty_group,
        )
        self.announcement.visibility_scope = "role_based"
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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AnnouncementCreateUpdateOnCommitTests(TestCase):
    """The create / update service path is wrapped in ``@transaction.atomic``.

    Earlier revisions ran ``send_announcement_email`` synchronously inside
    that atomic block, which meant:

      * The whole SMTP loop held an announcement row lock for the
        duration of the network I/O, and
      * Any DB error raised *after* the send had already gone out would
        roll back the ``AnnouncementDelivery`` audit row — re-introducing
        the exact failure mode the delivery tracking is supposed to fix.

    These tests pin the fix in place: the sender must be deferred via
    ``transaction.on_commit`` and must NOT fire when the surrounding
    transaction rolls back.
    """

    def setUp(self):
        self.author = User.objects.create_user(
            email="onc-author@example.com",
            password="testpass",
            first_name="OC",
            last_name="Author",
        )

    def test_create_with_send_email_defers_send_until_commit(self):
        """Inside the atomic block, the send is *scheduled* but not yet
        invoked. Once the transaction commits, on_commit fires it exactly
        once for the announcement we just created."""
        with patch(
            "apps.admin.services.announcement.send_announcement_email"
        ) as mock_send:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                result = create_announcement(
                    {
                        "title": "Hello",
                        "body": "Body",
                        "send_email": True,
                    },
                    initiated_by=self.author,
                )
            # While callbacks are captured but not executed, the sender
            # must not have run — proves it is wired through on_commit.
            mock_send.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            announcement_id = result["data"]["id"]

            # Now execute the deferred callback and confirm the send is
            # invoked with the right announcement id and initiator.
            for cb in callbacks:
                cb()
            mock_send.assert_called_once()
            call = mock_send.call_args
            args, kwargs = call.args, call.kwargs
            self.assertEqual(args[0] if args else kwargs["announcement_id"], announcement_id)
            self.assertEqual(kwargs.get("initiated_by"), self.author)

    def test_create_send_email_is_dropped_on_rollback(self):
        """If the outer transaction rolls back, the on_commit callback is
        discarded — we must NOT notify recipients about an announcement
        that doesn't actually exist, and no AnnouncementDelivery row
        should be created."""
        with patch(
            "apps.admin.services.announcement.send_announcement_email"
        ) as mock_send:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        create_announcement(
                            {
                                "title": "Doomed",
                                "body": "Body",
                                "send_email": True,
                            },
                            initiated_by=self.author,
                        )
                        raise RuntimeError("force rollback")
                except RuntimeError:
                    pass

        mock_send.assert_not_called()
        self.assertFalse(
            Announcement.objects.filter(title="Doomed").exists(),
        )
        self.assertFalse(AnnouncementDelivery.objects.exists())

    def test_update_with_send_email_defers_send_until_commit(self):
        announcement = Announcement.objects.create(
            author_user=self.author,
            title="Existing",
            body="Body",
            visibility_scope="global",
        )

        with patch(
            "apps.admin.services.announcement.send_announcement_email"
        ) as mock_send:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                update_announcement(
                    announcement.id,
                    {"title": "Existing v2", "send_email": True},
                    initiated_by=self.author,
                )
            mock_send.assert_not_called()
            self.assertEqual(len(callbacks), 1)

            for cb in callbacks:
                cb()
            mock_send.assert_called_once()
            call = mock_send.call_args
            args, kwargs = call.args, call.kwargs
            self.assertEqual(args[0] if args else kwargs["announcement_id"], announcement.id)

    def test_create_without_send_email_schedules_nothing(self):
        """Sanity: ``send_email`` opt-in is required to schedule a send."""
        with patch(
            "apps.admin.services.announcement.send_announcement_email"
        ) as mock_send:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                create_announcement(
                    {"title": "Silent", "body": "Body"},
                    initiated_by=self.author,
                )
            self.assertEqual(callbacks, [])
            mock_send.assert_not_called()

    def test_delivery_row_survives_commit_path(self):
        """End-to-end: when the outer transaction commits, the deferred
        ``send_announcement_email`` runs in autocommit mode and the
        resulting ``AnnouncementDelivery`` row is durable — not subject
        to the create's atomic block. This is the audit-trail guarantee
        we re-established by moving the send out of @transaction.atomic.
        """
        with self.captureOnCommitCallbacks(execute=True):
            result = create_announcement(
                {
                    "title": "Audited",
                    "body": "Body",
                    "send_email": True,
                },
                initiated_by=self.author,
            )
        announcement_id = result["data"]["id"]
        # The real sender ran (the locmem backend accepts everything),
        # so a delivery row must be visible from outside the create's
        # transaction.
        deliveries = AnnouncementDelivery.objects.filter(
            announcement_id=announcement_id,
        )
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(
            deliveries.first().status, AnnouncementDelivery.Status.SUCCESS,
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AnnouncementEmailHtmlBodyTests(TestCase):
    """The send path attaches a styled HTML alternative; cover its shape."""

    def setUp(self):
        from django.core import mail

        mail.outbox = []
        self.author = User.objects.create_user(
            email="author@example.com",
            password="testpass",
            first_name="An",
            last_name="Author",
        )
        self.recipient = User.objects.create_user(
            email="r@example.com",
            password="testpass",
            first_name="R",
            last_name="One",
        )

    def _send(self, *, title="Hello", body="<p>This is the body.</p>"):
        from django.core import mail

        announcement = Announcement.objects.create(
            author_user=self.author,
            title=title,
            body=body,
            visibility_scope="global",
        )
        send_announcement_email(announcement.id, initiated_by=self.author)
        return mail.outbox, announcement

    def test_email_attaches_html_alternative(self):
        outbox, _ = self._send()
        self.assertGreaterEqual(len(outbox), 1)
        message = outbox[0]
        # Plain-text body is always set; the HTML alternative is what we care
        # about — without it, mail clients render the raw HTML markup as text.
        self.assertEqual(len(message.alternatives), 1)
        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertTrue(html_body.lstrip().startswith("<!doctype html>"))
        self.assertIn("<html", html_body)
        self.assertIn("</html>", html_body)

    def test_html_body_contains_title_and_excerpt(self):
        outbox, _ = self._send(
            title="Mid-term update",
            body="<p>Lab tour moved to <strong>Friday</strong>.</p>",
        )
        html_body, _ = outbox[0].alternatives[0]
        # Title is rendered into the dark header band.
        self.assertIn("Mid-term update", html_body)
        # Excerpt is HTML-stripped and re-escaped, so the <strong> tag from
        # the source body must not survive into the email markup.
        self.assertNotIn("<strong>Friday</strong>", html_body)
        self.assertIn("Friday", html_body)

    def test_html_body_escapes_xss_in_title(self):
        outbox, _ = self._send(title='<script>alert("xss")</script>Notice')
        html_body, _ = outbox[0].alternatives[0]
        # The raw tag must not appear; the escaped form must.
        self.assertNotIn('<script>alert("xss")</script>', html_body)
        self.assertIn("&lt;script&gt;", html_body)
        self.assertIn("Notice", html_body)

    def test_html_body_links_to_announcement_detail(self):
        outbox, announcement = self._send()
        html_body, _ = outbox[0].alternatives[0]
        # The CTA links to the announcement detail page. We don't pin the
        # exact host (settings-driven) — just assert the announcement id is
        # in the URL and that the link is wrapped in an anchor.
        self.assertIn(f"/{announcement.id}", html_body)
        self.assertIn("<a href=", html_body)
        self.assertIn("Read full announcement", html_body)

    def test_html_and_plain_text_share_subject(self):
        outbox, _ = self._send(title="Subject sanity")
        message = outbox[0]
        # Subject is plain text (no HTML escaping) and carries the title;
        # the brand prefix is set by settings.
        self.assertIn("Subject sanity", message.subject)
        self.assertNotIn("&lt;", message.subject)
        # The plain-text body carries the title too (mail clients without
        # HTML render it).
        self.assertIn("Subject sanity", message.body)
