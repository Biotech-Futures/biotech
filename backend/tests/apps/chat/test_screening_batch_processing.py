from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    dispatch_message_screening,
    process_suspicious_messages,
)
from apps.groups.models import Groups


class BatchProcessingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="batch-user@test.com",
            password="pw",
            first_name="Batch",
            last_name="User",
        )
        self.group = Groups.objects.create(group_name="Batch Group")

    def _queue(self, text):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )
        return dispatch_message_screening(message)

    def _queue_many(self, count):
        for index in range(count):
            self._queue(f"Distinct message number {index}")

    def _response(self, flagged):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "omni-moderation-latest",
            "results": [{
                "flagged": flagged,
                "categories": {"violence": flagged},
                "category_scores": {"violence": 0.97 if flagged else 0.02},
            }],
        }
        return response

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_limit_zero_falls_back_to_default_not_one(self, post):
        post.return_value = self._response(flagged=False)
        self._queue_many(3)

        counts = process_suspicious_messages(limit=0)

        self.assertEqual(counts["considered"], 3)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_negative_limit_is_raised_to_one(self, post):
        post.return_value = self._response(flagged=False)
        self._queue_many(3)

        counts = process_suspicious_messages(limit=-5)

        self.assertEqual(counts["considered"], 1)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_explicit_limit_caps_the_batch(self, post):
        post.return_value = self._response(flagged=False)
        self._queue_many(4)

        counts = process_suspicious_messages(limit=2)

        self.assertEqual(counts["considered"], 2)
        self.assertEqual(counts["safe"], 2)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_mixed_batch_counts_safe_flagged_and_failed(self, post):
        # Records are processed oldest first, so the order of queueing
        # matches the order of the mocked responses below.
        self._queue("First message in the batch")
        self._queue("Second message in the batch")
        self._queue("Third message in the batch")
        post.side_effect = [
            self._response(flagged=False),
            self._response(flagged=True),
            RuntimeError("moderation unavailable"),
        ]

        counts = process_suspicious_messages()

        self.assertEqual(
            counts,
            {"considered": 3, "safe": 1, "flagged": 1, "failed": 1},
        )

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_deleted_messages_are_skipped(self, post):
        post.return_value = self._response(flagged=False)
        kept = self._queue("This message stays")
        removed = self._queue("This message is deleted")
        Messages.objects.filter(pk=removed.message_id).update(
            deleted_at=timezone.now()
        )

        counts = process_suspicious_messages()

        self.assertEqual(counts["considered"], 1)
        removed.refresh_from_db()
        self.assertEqual(removed.status, MessageScreeningStatus.SUSPICIOUS)
        kept.refresh_from_db()
        self.assertEqual(kept.status, MessageScreeningStatus.SAFE)
