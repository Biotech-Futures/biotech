"""Send 24h-out RSVP reminder emails.

Triggered by an external scheduler (the hourly GitHub Actions workflow
in ``.github/workflows/rsvp-reminders.yml``, or manually for ops). All
business logic lives in ``apps.events.services.send_due_rsvp_reminders``
so the HTTP endpoint and this command stay in lockstep.
"""

from django.core.management.base import BaseCommand

from apps.events.services import send_due_rsvp_reminders


class Command(BaseCommand):
    help = "Send RSVP reminder emails for events starting in ~24h."

    def handle(self, *args, **options):
        events_processed, sent, failed = send_due_rsvp_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"RSVP reminders: events={events_processed} "
                f"sent={sent} failed={failed}"
            )
        )
