"""Each send keeps who it was addressed to and whether it reached them, so
admins can export an email's recipients and find the emails sent to someone."""
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from apps.services.email_log import note_send
from apps.services.email_metrics import record_email_delivery
from apps.services.models import EmailDeliveryMetric, EmailDeliveryRecipient
from apps.users.models import User


class RecordRecipientsTests(TestCase):
    def setUp(self):
        self.amy = User.objects.create_user(email="amy@example.com", password="pw12345!", first_name="Amy")

    def rows(self):
        return {
            row.email: (row.status, row.reason, row.user_id)
            for row in EmailDeliveryRecipient.objects.all()
        }

    def test_keeps_one_row_per_address_with_its_outcome(self):
        record_email_delivery(
            "announcement",
            source_mailbox="info@biotechfutures.org",
            attempted=3,
            delivered=2,
            failed=1,
            recipients=["Amy@Example.com", "bo@example.com", "Guardian <g@outside.test>", "amy@example.com"],
            missed={"bo@example.com": "address refused"},
        )

        metric = EmailDeliveryMetric.objects.get()
        self.assertEqual(metric.recipients.count(), 3)
        self.assertEqual(self.rows(), {
            "amy@example.com": ("delivered", "", self.amy.id),
            "bo@example.com": ("failed", "address refused", None),
            "g@outside.test": ("delivered", "", None),
        })

    def test_missed_addresses_are_kept_even_without_a_recipient_list(self):
        record_email_delivery(
            "unread_messages",
            source_mailbox="connect@biotechfutures.org",
            attempted=1,
            delivered=0,
            failed=1,
            missed={"amy@example.com": "lost the mail server connection"},
        )

        self.assertEqual(self.rows(), {
            "amy@example.com": ("failed", "lost the mail server connection", self.amy.id),
        })

    def test_counts_alone_keep_no_recipients(self):
        record_email_delivery(
            "announcement", source_mailbox="info@biotechfutures.org", attempted=2, delivered=2, failed=0,
        )

        self.assertTrue(EmailDeliveryMetric.objects.exists())
        self.assertFalse(EmailDeliveryRecipient.objects.exists())

    def test_the_counts_stay_when_the_recipient_list_cannot_be_written(self):
        with mock.patch.object(
            EmailDeliveryRecipient.objects, "bulk_create", side_effect=DatabaseError("full"),
        ):
            record_email_delivery(
                "announcement",
                source_mailbox="info@biotechfutures.org",
                attempted=1,
                delivered=1,
                failed=0,
                recipients=["amy@example.com"],
            )

        self.assertEqual(EmailDeliveryMetric.objects.get().delivered_count, 1)
        self.assertFalse(EmailDeliveryRecipient.objects.exists())

    def test_note_send_passes_the_recipients_on(self):
        note_send(
            "rsvp_reminder",
            missed={"bo@example.com": "address refused"},
            attempted=2,
            delivered=1,
            failed=1,
            source_mailbox="info@biotechfutures.org",
            recipients=["amy@example.com", "bo@example.com"],
        )

        self.assertEqual(self.rows(), {
            "amy@example.com": ("delivered", "", self.amy.id),
            "bo@example.com": ("failed", "address refused", None),
        })
