from django.core.management.base import BaseCommand, CommandError

from apps.system_logs.services import prune


class Command(BaseCommand):
    help = "Delete System Logs rows older than SYSTEM_LOG_RETENTION_DAYS (or --days)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Keep this many days instead of SYSTEM_LOG_RETENTION_DAYS.",
        )

    def handle(self, *args, days=None, **options):
        try:
            deleted = prune(days)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Deleted {deleted} system log entries.")
