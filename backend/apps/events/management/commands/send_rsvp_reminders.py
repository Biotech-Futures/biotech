"""Ops-side entrypoint for the RSVP reminder dispatcher.

Used for ad-hoc / dry-run invocations. The hourly cron path is the
GitHub Actions workflow hitting the HTTP trigger endpoint, which calls
the same apps.events.services.send_due_rsvp_reminders() service.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.events.services import REMINDER_KINDS, send_due_rsvp_reminders


class Command(BaseCommand):
    help = "Send RSVP reminder emails for events in their reminder windows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kind",
            choices=sorted(REMINDER_KINDS.keys()),
            default=None,
            help="Run only this reminder kind. Default: run every configured kind.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without claiming any row or sending email.",
        )

    def handle(self, *args, **options):
        try:
            events, sent, failed = send_due_rsvp_reminders(
                kind=options["kind"],
                dry_run=options["dry_run"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        kind_label = options["kind"] or "all"
        dry_label = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"RSVP reminders kind={kind_label}{dry_label}: "
                f"events={events} sent={sent} failed={failed}"
            )
        )
