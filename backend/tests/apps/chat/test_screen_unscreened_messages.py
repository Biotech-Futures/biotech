from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.chat.models import MessageScreening, Messages
from apps.chat.services.screening import dispatch_message_screening
from apps.groups.models import Groups


class ScreenUnscreenedMessagesCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="screening-command@test.com",
            password="pw",
        )
        self.group = Groups.objects.create(group_name="Screening Command Group")

    def _message(self, text):
        return Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )

    def test_limit_counts_new_screenings_not_old_messages(self):
        already_screened = self._message("Already processed")
        dispatch_message_screening(already_screened)
        first_new = self._message("First new message")
        second_new = self._message("Second new message")

        call_command("screen_unscreened_messages", limit=1, stdout=StringIO())

        self.assertTrue(MessageScreening.objects.filter(message=first_new).exists())
        self.assertFalse(MessageScreening.objects.filter(message=second_new).exists())

    def test_dry_run_reports_without_writing(self):
        self._message("One")
        self._message("Two")
        stdout = StringIO()

        call_command(
            "screen_unscreened_messages",
            limit=10,
            dry_run=True,
            stdout=stdout,
        )

        self.assertEqual(MessageScreening.objects.count(), 0)
        self.assertIn("2 message(s) would be screened", stdout.getvalue())
