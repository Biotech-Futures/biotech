from django.core.management.base import BaseCommand

from apps.chat.models import MessageScreening, MessageScreeningStatus
from apps.chat.services.screening import process_suspicious_messages


class Command(BaseCommand):
    help = "Send queued chat messages to the configured AI moderation API."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        if options["dry_run"]:
            qs = MessageScreening.objects.filter(
                status=MessageScreeningStatus.SUSPICIOUS,
                message__deleted_at__isnull=True,
            )
            count = min(qs.count(), limit) if limit else qs.count()
            self.stdout.write(f"Dry run: {count} queued message(s) would be sent to AI.")
            return

        counts = process_suspicious_messages(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"AI screening complete: {counts}"))
