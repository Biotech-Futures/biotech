from django.core.management.base import BaseCommand

from apps.users.guardian_reminders import send_due


class Command(BaseCommand):
    help = (
        "Email the consent form to every guardian due a reminder today. The "
        "daily scheduler calls the same run (see apps.users.guardian_reminders)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count who is due without emailing anyone.")

    def handle(self, *args, **options):
        result = send_due(dry_run=options["dry_run"])
        if result.get("disabled"):
            self.stdout.write("Automatic guardian reminders are switched off.")
            return
        self.stdout.write(
            f"Sent {result['sent']} guardian reminders, {result['failed']} failed, {result['skipped']} skipped."
        )
