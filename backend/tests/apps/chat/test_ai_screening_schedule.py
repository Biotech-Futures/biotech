from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.chat.models import MessageScreeningStatus, Messages
from apps.chat.services.screening import dispatch_message_screening
from apps.groups.models import Groups


class AiScreeningScheduleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="ai-schedule@test.com",
            password="pw",
        )
        self.group = Groups.objects.create(group_name="AI Schedule Group")
        self.url = reverse("run-ai-screening")

    def _queue_suspicious(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="This is a threat.",
        )
        return dispatch_message_screening(message)

    @override_settings(
        AI_SCREENING_TRIGGER_TOKEN="cron-secret",
        OPENAI_API_KEY="test-key",
    )
    @patch("apps.chat.services.screening.dispatch_suspicious_message_screening")
    def test_valid_cron_token_dispatches_batch(self, dispatch):
        dispatch.return_value = "started"

        response = self.client.post(
            self.url,
            HTTP_X_AI_SCREENING_TOKEN="cron-secret",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "started"})
        dispatch.assert_called_once_with()

    @override_settings(
        AI_SCREENING_TRIGGER_TOKEN="cron-secret",
        OPENAI_API_KEY="test-key",
    )
    def test_invalid_cron_token_is_rejected(self):
        response = self.client.post(
            self.url,
            HTTP_X_AI_SCREENING_TOKEN="wrong",
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(AI_SCREENING_TRIGGER_TOKEN="", OPENAI_API_KEY="")
    def test_missing_production_configuration_fails_loud(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)

    def test_dry_run_counts_queued_messages_without_calling_ai(self):
        screening = self._queue_suspicious()
        self.assertEqual(screening.status, MessageScreeningStatus.SUSPICIOUS)
        stdout = StringIO()

        with patch("apps.chat.services.screening.requests.post") as post:
            call_command(
                "screen_suspicious_messages",
                dry_run=True,
                stdout=stdout,
            )

        post.assert_not_called()
        self.assertIn("1 queued message(s)", stdout.getvalue())
