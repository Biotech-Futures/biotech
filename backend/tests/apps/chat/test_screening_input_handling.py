from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages
from apps.chat.services.screening import (
    _minimal_ai_input,
    _redact_personal_data,
    dispatch_message_screening,
    screen_message,
    should_screen_message,
)
from apps.groups.models import Groups


class ScreeningFixtureMixin:
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="input-handling@test.com",
            password="pw",
            first_name="Input",
            last_name="Handling",
        )
        self.group = Groups.objects.create(group_name="Input Handling Group")

    def _message(self, text):
        return Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )

    def _set_status(self, screening, status):
        MessageScreening.objects.filter(pk=screening.pk).update(status=status)


class ShouldScreenMessageTests(ScreeningFixtureMixin, TestCase):
    def test_new_message_should_be_screened(self):
        self.assertTrue(should_screen_message(self._message("Hello team.")))

    def test_deleted_message_is_not_screened(self):
        message = self._message("Hello team.")
        message.deleted_at = timezone.now()

        self.assertFalse(should_screen_message(message))

    def test_whitespace_only_message_is_not_screened(self):
        self.assertFalse(should_screen_message(self._message("   \n\t ")))

    def test_message_already_queued_is_not_screened_again(self):
        message = self._message("Hello team.")
        dispatch_message_screening(message)

        self.assertFalse(should_screen_message(message))

    def test_message_already_judged_safe_is_not_screened_again(self):
        message = self._message("Hello team.")
        screening = dispatch_message_screening(message)
        self._set_status(screening, MessageScreeningStatus.SAFE)

        self.assertFalse(should_screen_message(message))

    def test_failed_message_is_allowed_back_into_the_queue(self):
        message = self._message("Hello team.")
        screening = dispatch_message_screening(message)
        self._set_status(screening, MessageScreeningStatus.FAILED)

        self.assertTrue(should_screen_message(message))

    def test_screen_message_resets_failed_record_to_suspicious(self):
        message = self._message("Hello team.")
        screening = dispatch_message_screening(message)
        self._set_status(screening, MessageScreeningStatus.FAILED)

        again = screen_message(message)

        self.assertEqual(again.status, MessageScreeningStatus.SUSPICIOUS)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 1)


class RedactPersonalDataTests(SimpleTestCase):
    def test_email_addresses_are_redacted(self):
        cases = {
            "Reach me at student@example.com today": "Reach me at [EMAIL_ADDRESS] today",
            "STUDENT@EXAMPLE.COM": "[EMAIL_ADDRESS]",
            "a.b+tag@mail.example.org and c@d.io": "[EMAIL_ADDRESS] and [EMAIL_ADDRESS]",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(_redact_personal_data(text), expected)

    def test_phone_numbers_are_redacted(self):
        cases = {
            "Call +61 412 345 678 now": "Call [PHONE_NUMBER] now",
            "Call 0412 345 678 please": "Call [PHONE_NUMBER] please",
            "0412-345-678": "[PHONE_NUMBER]",
            "123456789": "[PHONE_NUMBER]",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(_redact_personal_data(text), expected)

    def test_text_without_contact_details_is_left_alone(self):
        for text in [
            "Room 12345 at 3pm",
            "12345678",
            "ref123456789",
            "No contact details here.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(_redact_personal_data(text), text)

    def test_empty_and_none_input(self):
        self.assertEqual(_redact_personal_data(""), "")
        self.assertEqual(_redact_personal_data(None), "")


class MinimalAiInputTests(ScreeningFixtureMixin, TestCase):
    @override_settings(AI_SCREENING_MAX_INPUT_CHARS=10)
    def test_input_is_truncated_to_the_configured_limit(self):
        screening = dispatch_message_screening(
            self._message("abcdefghijklmnopqrstuvwxyz")
        )

        self.assertEqual(_minimal_ai_input(screening), "abcdefghij")

    @override_settings(AI_SCREENING_MAX_INPUT_CHARS=0)
    def test_zero_limit_is_raised_to_one_character(self):
        screening = dispatch_message_screening(self._message("abcdef"))

        self.assertEqual(_minimal_ai_input(screening), "a")

    @override_settings(AI_SCREENING_MAX_INPUT_CHARS=20)
    def test_contact_data_is_redacted_before_truncation(self):
        screening = dispatch_message_screening(
            self._message("Reach me at student@example.com")
        )

        result = _minimal_ai_input(screening)

        self.assertEqual(result, "Reach me at [EMAIL_A")
        self.assertNotIn("student", result)
        self.assertNotIn("example", result)
