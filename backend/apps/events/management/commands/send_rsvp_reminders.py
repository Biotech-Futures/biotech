from django.core.management.base import BaseCommand

from apps.events.tasks import send_event_rsvp_reminders


class Command(BaseCommand):
    help = "Send RSVP reminder emails for events starting in approximately 24 hours"

    def handle(self, *args, **options):
        self.stdout.write("Sending RSVP reminders...")
        send_event_rsvp_reminders()
        self.stdout.write(self.style.SUCCESS("Done."))