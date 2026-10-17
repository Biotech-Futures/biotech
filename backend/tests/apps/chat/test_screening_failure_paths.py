from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.chat.models import MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    dispatch_message_screening,
    screen_suspicious_message,
)
from apps.groups.models import Groups


class FailurePathTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="failure-paths@test.com",
            password="pw",
            first_name="Failure",
            last_name="Paths",
        )
        self.group = Groups.objects.create(group_name="Failure Paths Group")

    def _queued(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="This is a threat.",
        )
        return dispatch_message_screening(message)

    def _response(self, payload):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_malformed_moderation_payload_keeps_record_retryable(self, post):
        screening = self._queued()
        payloads = [
            {},
            {"results": []},
            {"results": None},
            {"results": ["not-a-dict"]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                post.return_value = self._response(payload)

                result = screen_suspicious_message(screening.id)

                self.assertIsNone(result)
                screening.refresh_from_db()
                self.assertEqual(
                    screening.status, MessageScreeningStatus.SUSPICIOUS
                )
                self.assertIn("did not contain a result", screening.error_message)

    @override_settings(OPENAI_API_KEY="")
    @patch("apps.chat.services.screening.requests.post")
    def test_missing_api_key_fails_without_calling_the_api(self, post):
        screening = self._queued()

        result = screen_suspicious_message(screening.id)

        self.assertIsNone(result)
        post.assert_not_called()
        screening.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertIn("not configured", screening.error_message)

    def test_unknown_screening_id_returns_none(self):
        self.assertIsNone(screen_suspicious_message(999999))

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_http_error_keeps_record_retryable(self, post):
        screening = self._queued()
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests"
        )
        post.return_value = response

        result = screen_suspicious_message(screening.id)

        self.assertIsNone(result)
        screening.refresh_from_db()
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(screening.attempt_count, 1)
        self.assertIn("429", screening.error_message)
