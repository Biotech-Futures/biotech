from django.core.management.base import BaseCommand

from apps.chat.models import Messages
from apps.chat.services.screening import dispatch_message_screening


class Command(BaseCommand):
    help = "Screen chat messages that do not yet have a screening record for their current text."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 5000))
        dry_run = options["dry_run"]
        qs = (
            Messages.objects
            .filter(deleted_at__isnull=True)
            .select_related("group", "sender_user")
            .order_by("id")[:limit]
        )

        screened = 0
        skipped = 0
        for message in qs:
            if dry_run:
                result = None
            else:
                result = dispatch_message_screening(message)
            if result is None:
                skipped += 1
            else:
                screened += 1

        if dry_run:
            self.stdout.write(f"Dry run inspected up to {limit} messages.")
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Screening complete. Created/updated {screened}; skipped {skipped}."
            )
        )
