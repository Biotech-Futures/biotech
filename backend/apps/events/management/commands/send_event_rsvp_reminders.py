from django.core.management.base import BaseCommand

from apps.events.services import send_due_event_rsvp_reminders


class Command(BaseCommand):
    help = "Send RSVP reminder emails for events starting about 24 hours from now."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours-ahead",
            type=int,
            default=None,
            help="Override how many hours ahead to target. Defaults to settings.",
        )
        parser.add_argument(
            "--window-hours",
            type=int,
            default=None,
            help="Override the reminder window width. Defaults to settings.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which events would be processed without sending email.",
        )

    def handle(self, *args, **options):
        summary = send_due_event_rsvp_reminders(
            hours_ahead=options["hours_ahead"],
            window_hours=options["window_hours"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Processed {events_considered} due event(s); marked={events_marked}, "
                "sent={emails_sent}, failed={emails_failed}, skipped={emails_skipped}, "
                "dry_run={dry_run}".format(**summary)
            )
        )

