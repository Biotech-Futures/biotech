"""Send RSVP reminder emails.

Runs two passes:
  * 24h window — full reminder for ACCEPTED + nudge for PENDING
  * 1h window  — final reminder for ACCEPTED only

Triggered by an external scheduler (the hourly GitHub Actions workflow
in ``.github/workflows/rsvp-reminders.yml``, or manually for ops). All
business logic lives in ``apps.events.services.send_due_rsvp_reminders``
so the HTTP endpoint and this command stay in lockstep.
"""

from django.core.management.base import BaseCommand

from apps.events.services import (
    send_due_rsvp_reminders,
    RSVP_REMINDER_24H_WINDOW_START,
    RSVP_REMINDER_24H_WINDOW_END,
    RSVP_REMINDER_1H_WINDOW_START,
    RSVP_REMINDER_1H_WINDOW_END,
)


class Command(BaseCommand):
    help = "Send RSVP reminder emails for events starting in ~24h and ~1h."

    def handle(self, *args, **options):
        # 24h pass — confirmed attendees + pending nudge
        events_24h, sent_24h, failed_24h = send_due_rsvp_reminders(
            window_start_hours=RSVP_REMINDER_24H_WINDOW_START,
            window_end_hours=RSVP_REMINDER_24H_WINDOW_END,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"24h reminders: events={events_24h} sent={sent_24h} failed={failed_24h}"
            )
        )

        # 1h pass — confirmed attendees only
        events_1h, sent_1h, failed_1h = send_due_rsvp_reminders(
            window_start_hours=RSVP_REMINDER_1H_WINDOW_START,
            window_end_hours=RSVP_REMINDER_1H_WINDOW_END,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"1h reminders: events={events_1h} sent={sent_1h} failed={failed_1h}"
            )
        )