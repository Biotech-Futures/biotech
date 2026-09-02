"""Send the daily reminder to teams whose entry is still outstanding.

Run once a day on a schedule. It is safe to run more often than that, and safe
to re-run after a failure: a team already written to today is skipped, so a
retry cannot double up on them.

    python manage.py send_submission_reminders
    python manage.py send_submission_reminders --dry-run

``--dry-run`` reports who would be written to without sending anything and
without recording that they were reminded, which is the safe way to check a
schedule before it goes live.
"""
from django.core.management.base import BaseCommand

from apps.submissions.reminders import send_due_reminders, teams_due


class Command(BaseCommand):
    help = "Email teams whose submission is incomplete in the final week."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List who would be reminded without sending or recording anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            due = teams_due()
            for group, submission, closes_at in due:
                state = "no entry started" if submission is None else "entry incomplete"
                self.stdout.write(
                    f"  {group.group_name}: {state}, closes {closes_at:%Y-%m-%d %H:%M} UTC"
                )
            self.stdout.write(self.style.WARNING(f"{len(due)} team(s) would be reminded."))
            return

        result = send_due_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders sent: {result['sent']}. "
                f"Skipped (no students): {result['skipped']}. "
                f"Failed: {result['failed']}."
            )
        )
