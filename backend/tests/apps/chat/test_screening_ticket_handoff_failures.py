from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.chat.models import MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    dispatch_message_screening,
    screen_suspicious_message,
)
from apps.groups.models import Groups
from apps.tickets.models import Ticket


class TicketHandoffFailureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="handoff-user@test.com",
            password="pw",
            first_name="Handoff",
            last_name="User",
        )
        self.group = Groups.objects.create(group_name="Handoff Group")

    def _queued_screening(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="This is a threat.",
        )
        return dispatch_message_screening(message)

    def _flagged_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "omni-moderation-latest",
            "results": [{
                "flagged": True,
                "categories": {"violence": True},
                "category_scores": {"violence": 0.97},
            }],
        }
        return response

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.create_ticket_for_flagged_message")
    @patch("apps.chat.services.screening.requests.post")
    def test_ticket_creation_failure_rolls_back_to_suspicious(self, post, create_ticket):
        screening = self._queued_screening()
        post.return_value = self._flagged_response()
        create_ticket.side_effect = RuntimeError("ticket service down")

        result = screen_suspicious_message(screening.id)

        self.assertIsNone(result)
        screening.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertIsNone(screening.ticket_id)
        self.assertIn("ticket service down", screening.error_message)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_retry_after_ticket_failure_creates_exactly_one_ticket(self, post):
        screening = self._queued_screening()
        post.return_value = self._flagged_response()

        with patch(
            "apps.chat.services.screening.create_ticket_for_flagged_message",
            side_effect=RuntimeError("ticket service down"),
        ):
            self.assertIsNone(screen_suspicious_message(screening.id))

        retried = screen_suspicious_message(screening.id)

        self.assertEqual(retried.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(retried.ticket_id, Ticket.objects.get().id)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_already_flagged_record_is_not_screened_or_ticketed_again(self, post):
        screening = self._queued_screening()
        post.return_value = self._flagged_response()
        first = screen_suspicious_message(screening.id)
        self.assertEqual(first.status, MessageScreeningStatus.FLAGGED)
        post.reset_mock()

        second = screen_suspicious_message(screening.id)

        post.assert_not_called()
        self.assertEqual(second.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(Ticket.objects.count(), 1)
