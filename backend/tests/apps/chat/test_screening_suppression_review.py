from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import MessageScreeningStatus, Messages
from apps.chat.services.screening import dispatch_message_screening, screen_suspicious_message
from apps.groups.models import GroupMembership, Groups
from apps.tickets.models import SupportScope, TicketStatus


class ScreeningSuppressionReviewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.sender = User.objects.create_user(email="sender@example.com", password="pw")
        self.peer = User.objects.create_user(email="peer@example.com", password="pw")
        self.agent = User.objects.create_user(email="agent@example.com", password="pw")
        SupportScope.objects.create(user=self.agent)
        self.group = Groups.objects.create(group_name="Moderation group")
        GroupMembership.objects.create(user=self.sender, group=self.group)
        GroupMembership.objects.create(user=self.peer, group=self.group)
        self.message = Messages.objects.create(
            sender_user=self.sender,
            group=self.group,
            message_text="A message requiring review",
        )

    def _flagged_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "omni-moderation-latest",
            "results": [{
                "flagged": True,
                "categories": {"violence": True},
                "category_scores": {"violence": 0.91},
            }],
        }
        return response

    def _messages_url(self):
        return f"/chat/groups/{self.group.pk}/messages/"

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_suppressed_message_is_visible_only_to_its_sender(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screen_suspicious_message(screening.pk)

        self.client.force_login(self.sender)
        sender_items = self.client.get(self._messages_url()).data["items"]
        self.assertEqual([row["id"] for row in sender_items], [self.message.pk])
        self.assertTrue(sender_items[0]["is_suppressed"])

        self.client.force_login(self.peer)
        peer_items = self.client.get(self._messages_url()).data["items"]
        self.assertEqual(peer_items, [])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_ticket_includes_read_only_conversation_context_around_flagged_message(self, post):
        before = Messages.objects.create(
            sender_user=self.peer,
            group=self.group,
            message_text="What time should we meet?",
            sent_at=self.message.sent_at - timedelta(minutes=1),
        )
        after = Messages.objects.create(
            sender_user=self.peer,
            group=self.group,
            message_text="Can you explain what you mean?",
            sent_at=self.message.sent_at + timedelta(minutes=1),
        )
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screening = screen_suspicious_message(screening.pk)
        self.client.force_login(self.agent)

        response = self.client.get(f"/api/v1/admin/tickets/{screening.ticket_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        context = response.data["data"]["screeningReview"]["conversationContext"]
        self.assertEqual([row["id"] for row in context], [before.pk, self.message.pk, after.pk])
        self.assertEqual([row["isTarget"] for row in context], [False, True, False])
        self.assertEqual(context[1]["messageText"], "A message requiring review")
        self.assertTrue(context[1]["suppressed"])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_support_can_approve_and_restore_the_message_from_the_ticket(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screening = screen_suspicious_message(screening.pk)
        self.client.force_login(self.agent)

        response = self.client.post(
            f"/api/v1/admin/tickets/{screening.ticket_id}/screening-review/",
            {"decision": "approve"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["screeningReview"]["status"], "approved")
        self.assertEqual(
            response.data["data"]["screeningReview"]["messageText"],
            "A message requiring review",
        )
        self.assertEqual(
            response.data["data"]["screeningReview"]["sender"],
            {"id": self.sender.pk, "name": "sender@example.com"},
        )
        self.assertEqual(
            response.data["data"]["screeningReview"]["group"],
            {"id": self.group.pk, "name": "Moderation group"},
        )
        self.assertEqual(
            response.data["data"]["screeningReview"]["provider"],
            "omni-moderation-latest",
        )
        self.assertEqual(response.data["data"]["screeningReview"]["category"], "violence")
        self.assertEqual(
            response.data["data"]["screeningReview"]["reason"],
            "OpenAI moderation flagged: violence",
        )
        self.assertIsNotNone(response.data["data"]["screeningReview"]["screenedAt"])
        self.assertFalse(response.data["data"]["screeningReview"]["suppressed"])
        screening.refresh_from_db()
        self.message.refresh_from_db()
        screening.ticket.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.APPROVED)
        self.assertEqual(screening.reviewed_by_id, self.agent.pk)
        self.assertFalse(self.message.is_suppressed)
        self.assertIsNone(self.message.deleted_at)
        self.assertEqual(screening.ticket.status, TicketStatus.RESOLVED)

        self.client.force_login(self.peer)
        ids = [row["id"] for row in self.client.get(self._messages_url()).data["items"]]
        self.assertEqual(ids, [self.message.pk])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_support_can_delete_the_message_from_the_ticket(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screening = screen_suspicious_message(screening.pk)
        self.client.force_login(self.agent)

        response = self.client.post(
            f"/api/v1/admin/tickets/{screening.ticket_id}/screening-review/",
            {"decision": "delete"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["screeningReview"]["status"], "rejected")
        screening.refresh_from_db()
        self.message.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.REJECTED)
        self.assertEqual(screening.reviewed_by_id, self.agent.pk)
        self.assertIsNotNone(self.message.deleted_at)
        self.assertEqual(self.message.deleted_by_id, self.agent.pk)

        self.client.force_login(self.sender)
        sender_items = self.client.get(self._messages_url()).data["items"]
        self.assertEqual([row["id"] for row in sender_items], [self.message.pk])
        self.assertTrue(sender_items[0]["is_deleted"])

        self.client.force_login(self.peer)
        peer_items = self.client.get(self._messages_url()).data["items"]
        self.assertEqual(peer_items, [])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_screening_decision_cannot_be_applied_twice(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screening = screen_suspicious_message(screening.pk)
        self.client.force_login(self.agent)
        url = f"/api/v1/admin/tickets/{screening.ticket_id}/screening-review/"

        first = self.client.post(url, {"decision": "approve"}, format="json")
        second = self.client.post(url, {"decision": "delete"}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_group_member_cannot_make_the_ticket_decision(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screening = screen_suspicious_message(screening.pk)
        self.client.force_login(self.peer)

        response = self.client.post(
            f"/api/v1/admin/tickets/{screening.ticket_id}/screening-review/",
            {"decision": "approve"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        screening.refresh_from_db()
        self.message.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.FLAGGED)
        self.assertTrue(self.message.is_suppressed)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_suppressed_message_cannot_be_managed_from_the_group(self, post):
        screening = dispatch_message_screening(self.message)
        post.return_value = self._flagged_response()
        screen_suspicious_message(screening.pk)
        self.client.force_login(self.sender)
        detail_url = f"{self._messages_url()}{self.message.pk}/"

        edit = self.client.patch(detail_url, {"message_text": "changed"}, format="json")
        delete = self.client.delete(detail_url)

        self.assertIn(edit.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})
        self.assertIn(delete.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})
        self.message.refresh_from_db()
        self.assertEqual(self.message.message_text, "A message requiring review")
        self.assertIsNone(self.message.deleted_at)
