"""Ops-side entrypoint for the unread-chat-messages email digest.

Used for ad-hoc / dry-run invocations. The daily production path is the GitHub
Actions workflow hitting the HTTP trigger endpoint, which calls the same
apps.chat.services.digest.send_unread_message_digests() service.
"""

from django.core.management.base import BaseCommand

from apps.chat.services.digest import send_unread_message_digests


class Command(BaseCommand):
    help = "Send the daily 'you have unread messages' email digest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would be emailed without claiming state or sending email.",
        )

    def handle(self, *args, **options):
        considered, sent, failed = send_unread_message_digests(
            dry_run=options["dry_run"],
        )
        dry_label = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Unread digest{dry_label}: "
                f"considered={considered} sent={sent} failed={failed}"
            )
        )
