"""Submit complete drafts whose team is past its cut-off; safe to re-run.

    python manage.py auto_submit_entries [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.submissions.autosubmit import auto_submit_due


class Command(BaseCommand):
    help = "Submit complete, never-submitted drafts once each team's cut-off has passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the teams that would be submitted without changing anything.",
        )

    def handle(self, *args, dry_run, **options):
        result = auto_submit_due(dry_run=dry_run)
        for name in result["submitted"]:
            self.stdout.write(f"  {name}")
        verb = "Would submit" if dry_run else "Submitted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {len(result['submitted'])} team(s)."))
