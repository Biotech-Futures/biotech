import json
from datetime import datetime, timezone as datetime_timezone
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.resources.models import RoleAssignmentHistory, Roles

User = get_user_model()

URL = "/api/v1/assistant/ask/"


def openai_reply(answer="", answered=True, links=(), status="completed", refusal=None):
    if refusal is not None:
        content = [{"type": "refusal", "refusal": refusal}]
    else:
        text = json.dumps({"answer": answer, "answered": answered, "links": list(links)})
        content = [{"type": "output_text", "text": text, "annotations": []}]
    response = MagicMock(ok=True)
    response.json.return_value = {
        "status": status,
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "role": "assistant", "content": content},
        ],
        "usage": {
            "input_tokens": 10, "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 2},
        },
    }
    return response


@override_settings(OPENAI_API_KEY="test-key")
class AssistantOpenAITests(APITestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("apps.assistant.llm.requests.post")
        self.post = patcher.start()
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
        return self.post.call_args.kwargs["json"]

    def test_answers_with_openai(self):
        self.post.return_value = openai_reply("Open Resources in the menu.", links=["/resources"])
        response = self.ask()
        self.assertEqual(response.data, {
            "answer": "Open Resources in the menu.",
            "links": [{"label": "Resources", "to": "/resources"}],
            "matched": True,
        })

    def test_sends_only_the_question_and_the_role_guide(self):
        self.post.return_value = openai_reply("Open Resources.")
        self.ask("Where are the resources?")
        developer, user = self.sent()["input"]
        self.assertEqual(user, {"role": "user", "content": "Where are the resources?"})
        self.assertEqual(developer["role"], "developer")
        self.assertIn("Open Resources in the menu", developer["content"])
        self.assertNotIn("Import Students CSV", developer["content"])
        # Guide lines carry their topics, so "What should I do?" finds its entry.
        self.assertIn("- (what should i do, ", developer["content"])
        self.assertNotIn("s@example.com", json.dumps(self.sent()))
        self.assertIs(self.sent()["store"], False)

    def test_drops_links_outside_the_role(self):
        self.post.return_value = openai_reply("See Users.", links=["/admin/users", "/resources"])
        self.assertEqual(self.ask().data["links"], [{"label": "Resources", "to": "/resources"}])

    def test_unanswered_question_points_to_support(self):
        self.post.return_value = openai_reply("I can only help with using the platform.", answered=False)
        response = self.ask("What's the weather tomorrow?")
        self.assertFalse(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Support", "to": "/support"}])

    def test_request_error_falls_back_to_faq(self):
        self.post.side_effect = requests.ConnectionError("down")
        with self.assertLogs("apps.assistant.views", "ERROR"):
            response = self.ask("How do I contact my mentor?")
        self.assertTrue(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    def test_refusal_falls_back_to_faq(self):
        self.post.return_value = openai_reply(refusal="I can't help with that.")
        response = self.ask("How do I contact my mentor?")
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    def test_cut_short_reply_falls_back_to_faq(self):
        self.post.return_value = openai_reply("Open your gr", status="incomplete")
        response = self.ask("How do I contact my mentor?")
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    @override_settings(OPENAI_API_KEY="")
    def test_without_a_key_openai_is_not_called(self):
        self.assertTrue(self.ask("How do I contact my mentor?").data["matched"])
        self.post.assert_not_called()
