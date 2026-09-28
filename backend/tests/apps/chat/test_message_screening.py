from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    dispatch_message_screening,
    schedule_message_screening,
    screen_suspicious_message,
)
from apps.groups.models import Groups
from apps.tickets.models import Ticket, TicketChannel, TicketPriority


class MessageScreeningServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="screening-user@test.com",
            password="pw",
            first_name="Screening",
            last_name="User",
        )
        self.group = Groups.objects.create(group_name="Screening Group")

    def _message(self, text):
        return Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )

    def _moderation_response(self, *, flagged, category="violence", score=0.97):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "omni-moderation-latest",
            "results": [{
                "flagged": flagged,
                "categories": {category: flagged},
                "category_scores": {category: score},
            }],
        }
        return response

    def test_every_plain_message_is_queued_for_ai(self):
        message = self._message("Hello team, this update looks good.")

        screening = dispatch_message_screening(message)

        self.assertIsNotNone(screening)
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(screening.message_snapshot, message.message_text)
        self.assertEqual(screening.group_id, self.group.id)
        self.assertEqual(screening.sender_user_id, self.user.id)

    def test_empty_and_system_messages_are_not_queued(self):
        blank = self._message("")
        system = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="Automated event",
            message_type="system",
        )

        self.assertIsNone(dispatch_message_screening(blank))
        self.assertIsNone(dispatch_message_screening(system))

    def test_same_message_text_is_not_screened_twice(self):
        message = self._message("No problems here.")

        first = dispatch_message_screening(message)
        second = dispatch_message_screening(message)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 1)

    @override_settings(OPENAI_API_KEY="")
    def test_schedule_creates_durable_queue_record_after_commit(self):
        message = self._message("Queue this message")

        with self.captureOnCommitCallbacks(execute=True):
            schedule_message_screening(message)

        screening = MessageScreening.objects.get(message=message)
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)

    def test_repeated_suspicious_message_does_not_create_duplicate_record(self):
        message = self._message("This is a threat.")

        first = dispatch_message_screening(message)
        second = dispatch_message_screening(message)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(MessageScreening.objects.count(), 1)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_ai_flag_creates_high_priority_ticket(self, post):
        message = self._message("This is a threat.")
        screening = dispatch_message_screening(message)
        post.return_value = self._moderation_response(flagged=True)

        result = screen_suspicious_message(screening.id)

        self.assertEqual(result.status, MessageScreeningStatus.FLAGGED)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.channel, TicketChannel.AI_SCREENING)
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertIsNone(ticket.created_by_id)
        self.assertEqual(ticket.body, message.message_text)
        self.assertIn("violence", ticket.subject)
        self.assertEqual(result.ticket_id, ticket.id)
        self.assertEqual(result.categories, {"violence": True})
        self.assertEqual(result.category_scores, {"violence": 0.97})
        self.assertEqual(result.attempt_count, 1)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_ai_safe_result_closes_queue_without_ticket(self, post):
        screening = dispatch_message_screening(self._message("This is a threat."))
        post.return_value = self._moderation_response(flagged=False, score=0.02)

        result = screen_suspicious_message(screening.id)

        self.assertEqual(result.status, MessageScreeningStatus.SAFE)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_ai_failure_stays_suspicious_and_can_be_retried(self, post):
        screening = dispatch_message_screening(self._message("This is a threat."))
        post.side_effect = RuntimeError("moderation unavailable")

        failed = screen_suspicious_message(screening.id)

        self.assertIsNone(failed)
        screening.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertIn("moderation unavailable", screening.error_message)

        post.side_effect = None
        post.return_value = self._moderation_response(flagged=True)
        retried = screen_suspicious_message(screening.id)

        self.assertEqual(retried.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(retried.error_message, "")
        self.assertEqual(Ticket.objects.count(), 1)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_ai_input_omits_identity_and_unrelated_reply_context(self, post):
        parent = self._message("Earlier context from parent@test.com")
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="This is a threat. Call 0400 000 000.",
            reply_to=parent,
        )
        screening = dispatch_message_screening(message)
        post.return_value = self._moderation_response(flagged=False)

        screen_suspicious_message(screening.id)

        sent_text = post.call_args.kwargs["json"]["input"]
        self.assertIn("This is a threat.", sent_text)
        self.assertNotIn("Earlier context", sent_text)
        self.assertIn("[PHONE_NUMBER]", sent_text)
        self.assertNotIn("0400 000 000", sent_text)
        self.assertNotIn("parent@test.com", sent_text)
        self.assertNotIn(self.user.email, sent_text)
        self.assertNotIn(self.user.first_name, sent_text)

    def test_personal_contact_pattern_is_queued_for_ai(self):
        screening = dispatch_message_screening(
            self._message("Email me at private@example.com")
        )

        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(screening.category, "")

    def test_edited_message_is_screened_again_when_text_changes(self):
        message = self._message("Original safe text.")
        first = dispatch_message_screening(message)

        message.message_text = "Edited text with a threat."
        message.edited_at = timezone.now()
        message.save(update_fields=["message_text", "edited_at"])
        second = dispatch_message_screening(message)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first.text_hash, second.text_hash)
        self.assertEqual(first.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(second.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 2)
        self.assertEqual(Ticket.objects.count(), 0)
