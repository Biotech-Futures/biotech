from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import APIException
from apps.users.models import StudentProfile
from apps.users.guardian_reminders import send_guardian_reminder


class Command(BaseCommand):
    help = "Send due guardian reminders. Schedule only after configuring the approved consent URL and interval."

    def handle(self, *args, **options):
        if getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0) <= 0:
            self.stdout.write("Automatic guardian reminders are disabled.")
            return
        sent = 0
        ids = StudentProfile.objects.filter(
            has_join_permission=False, guardian_reminder_due_at__lte=timezone.now(),
            user__account_status="active",
        ).values_list("user_id", flat=True)
        for user_id in ids.iterator():
            try:
                send_guardian_reminder(user_id)
                sent += 1
            except APIException:
                self.stderr.write(f"Reminder not sent for student {user_id}.")
        self.stdout.write(f"Sent {sent} guardian reminders.")
