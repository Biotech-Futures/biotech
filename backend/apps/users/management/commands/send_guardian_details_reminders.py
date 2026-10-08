"""Email today's students with no parent/guardian details; safe to re-run, as
students already emailed today are skipped.

    python manage.py send_guardian_details_reminders [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.users.guardian_details import send_due, students_due


class Command(BaseCommand):
    help = "Email students with no parent/guardian email on file, once a day."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List who would be emailed without sending or recording anything.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            due = list(students_due())
            for profile in due:
                self.stdout.write(f"  {profile.user.email}")
            self.stdout.write(self.style.WARNING(f"{len(due)} student(s) would be emailed."))
            return

        result = send_due()
        if result.get("disabled"):
            self.stdout.write(self.style.WARNING("The guardian details email is switched off."))
            return
        self.stdout.write(self.style.SUCCESS(f"Sent: {result['sent']}. Failed: {result['failed']}."))
