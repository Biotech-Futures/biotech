from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.chat.models import MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    dispatch_message_screening,
    run_external_ai_moderation,
)
from apps.groups.models import Groups


class ModerationEdgeCaseTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="screening-edge@test.com",
            password="pw",
            first_name="Screening",
            last_name="Edge",
        )
        self.group = Groups.objects.create(group_name="Screening Edge Group")

    def _message(self, text):
        return Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )

    def _raw_response(self, result):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "omni-moderation-latest",
            "results": [result],
        }
        return response

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_multiple_flagged_categories_pick_highest_score(self, post):
        screening = dispatch_message_screening(self._message("This is a threat."))
        post.return_value = self._raw_response({
            "flagged": True,
            "categories": {"violence": True, "harassment": True, "hate": False},
            "category_scores": {"violence": 0.91, "harassment": 0.97, "hate": 0.99},
        })

        verdict = run_external_ai_moderation(screening)

        self.assertEqual(verdict.category, "harassment")
        self.assertEqual(verdict.risk_score, Decimal("0.9700"))
        self.assertIn("violence", verdict.reason)
        self.assertIn("harassment", verdict.reason)
        self.assertNotIn("hate", verdict.reason)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_flagged_without_category_flags_falls_back_to_top_score(self, post):
        screening = dispatch_message_screening(self._message("This is a threat."))
        post.return_value = self._raw_response({
            "flagged": True,
            "categories": {"violence": False, "harassment": False},
            "category_scores": {"violence": 0.40, "harassment": 0.65},
        })

        verdict = run_external_ai_moderation(screening)

        self.assertEqual(verdict.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(verdict.category, "harassment")

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.chat.services.screening.requests.post")
    def test_safe_result_risk_score_is_highest_score_not_zero(self, post):
        screening = dispatch_message_screening(self._message("This is a threat."))
        post.return_value = self._raw_response({
            "flagged": False,
            "categories": {"violence": False, "harassment": False},
            "category_scores": {"violence": 0.12, "harassment": 0.31},
        })

        verdict = run_external_ai_moderation(screening)

        self.assertEqual(verdict.status, MessageScreeningStatus.SAFE)
        self.assertEqual(verdict.risk_score, Decimal("0.3100"))
