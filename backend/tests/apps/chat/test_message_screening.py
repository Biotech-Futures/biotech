from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages
from apps.chat.services.screening import dispatch_message_screening
from apps.common.text import sanitize_text
from apps.groups.models import Groups


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

    def test_safe_message_creates_safe_screening_record(self):
        message = self._message("Hello team, this update looks good.")

        screening = dispatch_message_screening(message)

        self.assertIsNotNone(screening)
        self.assertEqual(screening.status, MessageScreeningStatus.SAFE)
        self.assertEqual(screening.message_snapshot, message.message_text)
        self.assertEqual(screening.group_id, self.group.id)
        self.assertEqual(screening.sender_user_id, self.user.id)

    def test_masked_profanity_creates_flagged_screening_record(self):
        message = self._message("This contains *** for testing.")

        screening = dispatch_message_screening(message)

        self.assertEqual(screening.status, MessageScreeningStatus.FLAGGED)
        self.assertGreater(screening.risk_score, 0)
        self.assertEqual(screening.category, "masked_profanity")
        self.assertIn("***", screening.reason)

    def test_sanitized_blacklisted_word_is_flagged_by_replacement_token(self):
        sanitized = sanitize_text("This contains shit for testing.")
        message = self._message(sanitized)

        screening = dispatch_message_screening(message)

        self.assertEqual(message.message_text, "This contains *** for testing.")
        self.assertEqual(screening.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(screening.category, "masked_profanity")

    def test_same_message_text_is_not_screened_twice(self):
        message = self._message("No problems here.")

        first = dispatch_message_screening(message)
        second = dispatch_message_screening(message)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 1)

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
        self.assertEqual(second.status, MessageScreeningStatus.FLAGGED)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 2)
