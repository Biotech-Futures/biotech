"""Read the sending mailboxes' bounce notices and note who our emails didn't
reach (see ``apps.management.services.bounce_check``), by hand. In production
GitHub's schedule starts the same check about every 10 minutes
(``.github/workflows/bounce-check.yml``). It reads only what's new since its
last run, and never changes a mailbox. Does nothing until
``HOSTINGER_MAIL_API_KEY`` is set."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.management.services.bounce_check import check_bounces
from apps.services.hostinger_mail import MailApiError


class Command(BaseCommand):
    help = "Read the sending mailboxes' bounce notices and note who our emails didn't reach."

    def handle(self, *args, **options):
        if not settings.HOSTINGER_MAIL_API_KEY:
            self.stdout.write("HOSTINGER_MAIL_API_KEY isn't set: no mailboxes checked.")
            return
        try:
            result = check_bounces()
        except MailApiError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            f"Checked {result.mailboxes} mailbox(es): {result.notices} bounce notice(s) read, "
            f"{result.matched} of {result.bounces} bounce(s) matched to our emails."
        )
