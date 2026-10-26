import json
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.resources.models import RoleAssignmentHistory, Roles

User = get_user_model()

URL = "/api/v1/assistant/ask/"


def claude_reply(answer, answered=True, links=(), stop_reason="end_turn"):
    text = json.dumps({"answer": answer, "answered": answered, "links": list(links)})
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0,
        ),
    )


@override_settings(ANTHROPIC_API_KEY="test-key")
class AssistantClaudeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client_mock = MagicMock()
        patcher = patch("apps.assistant.llm._client", return_value=self.client_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.student = User.objects.create_user(email="s@example.com", password="pass1234")
        RoleAssignmentHistory.objects.create(
            user=self.student,
            role=Roles.objects.get_or_create(role_name="student")[0],
            valid_from=datetime(2025, 1, 1, tzinfo=datetime_timezone.utc),
        )
        self.client.force_login(self.student)

    def ask(self, question="Where are the resources?"):
        return self.client.post(URL, {"question": question}, format="json")

    def sent(self):
        return self.client_mock.messages.create.call_args.kwargs

    def test_answers_with_claude(self):
        self.client_mock.messages.create.return_value = claude_reply(
            "Open Resources in the menu.", links=["/resources"],
        )
        response = self.ask()
        self.assertEqual(response.data, {
            "answer": "Open Resources in the menu.",
            "links": [{"label": "Resources", "to": "/resources"}],
            "matched": True,
        })

    def test_sends_only_the_question_and_the_role_guide(self):
        self.client_mock.messages.create.return_value = claude_reply("Open Resources.")
        self.ask("Where are the resources?")
        self.assertEqual(self.sent()["messages"], [{"role": "user", "content": "Where are the resources?"}])
        [system] = self.sent()["system"]
        self.assertIn("Open Resources in the menu", system["text"])
        self.assertNotIn("Import Students CSV", system["text"])
        # Cached at the end of the shared prompt, before the question.
        self.assertEqual(system["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("s@example.com", json.dumps(self.sent()))

    def test_drops_links_outside_the_role(self):
        self.client_mock.messages.create.return_value = claude_reply(
            "See Users.", links=["/admin/users", "/resources"],
        )
        self.assertEqual(self.ask().data["links"], [{"label": "Resources", "to": "/resources"}])

    def test_unanswered_question_points_to_support(self):
        self.client_mock.messages.create.return_value = claude_reply(
            "I can only help with using the platform.", answered=False,
        )
        response = self.ask("What's the weather tomorrow?")
        self.assertFalse(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Support", "to": "/support"}])

    def test_api_error_falls_back_to_faq(self):
        self.client_mock.messages.create.side_effect = anthropic.AnthropicError("down")
        with self.assertLogs("apps.assistant.views", "ERROR"):
            response = self.ask("How do I contact my mentor?")
        self.assertTrue(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    def test_refusal_falls_back_to_faq(self):
        self.client_mock.messages.create.return_value = claude_reply("", stop_reason="refusal")
        response = self.ask("How do I contact my mentor?")
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    @override_settings(ANTHROPIC_API_KEY="")
    def test_without_a_key_claude_is_not_called(self):
        self.assertTrue(self.ask("How do I contact my mentor?").data["matched"])
        self.client_mock.messages.create.assert_not_called()
