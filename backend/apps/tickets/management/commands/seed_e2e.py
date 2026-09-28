"""Accounts the ticket E2E suite logs in with. Idempotent, dev-only.

The E2E tests drive real login forms, so they need real accounts with
known passwords. Rerunning always resets those passwords: a rehearsal
database that drifted (someone changed a password by hand) heals instead
of failing the whole suite at the login step.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tickets.models import SupportScope

STUDENT_EMAIL = "e2e.student@example.com"
AGENT_EMAIL = "e2e.agent@example.com"
# Not secrets: these exist only in DEBUG databases, and the E2E specs
# hard-code them on the other side of the login form.
STUDENT_PASSWORD = "E2eStudent1!"
AGENT_PASSWORD = "E2eAgent1!"


# Databases this command will write to without being forced. DEBUG alone is
# not enough of a guard: a developer's DEBUG environment normally points at
# the database they do their real work in, and this command overwrites
# passwords with published ones.
_SCRATCH_DB_MARKERS = ("rehearsal", "test", "e2e", "scratch")


class Command(BaseCommand):
    help = "Create (or reset) the accounts the ticket E2E suite uses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Seed even when the database name looks like a working one.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            # There is no state in which production wants accounts with
            # published passwords.
            raise CommandError("seed_e2e refuses to run with DEBUG off.")

        name = settings.DATABASES["default"]["NAME"] or ""
        if not any(m in str(name).lower() for m in _SCRATCH_DB_MARKERS):
            if not options["force"]:
                raise CommandError(
                    f'Database "{name}" does not look like a scratch database '
                    "(expected one of: "
                    + ", ".join(_SCRATCH_DB_MARKERS)
                    + "). Re-run with --force if that is really where the E2E "
                    "accounts should go."
                )
            self.stdout.write(self.style.WARNING(f'Forced onto "{name}".'))

        User = get_user_model()

        student, _ = User.objects.get_or_create(
            email=STUDENT_EMAIL,
            defaults={"first_name": "Stella", "last_name": "Nguyen"},
        )
        student.set_password(STUDENT_PASSWORD)
        student.save()
        # activate() rather than is_active=True: the model says in as many
        # words that setting one of the two status fields relies on a
        # compatibility shim new code must not use.
        student.activate()

        agent, _ = User.objects.get_or_create(
            email=AGENT_EMAIL,
            defaults={"first_name": "Sam", "last_name": "Reid"},
        )
        agent.set_password(AGENT_PASSWORD)
        agent.save()
        agent.activate()
        # Support-capable but NOT an admin: the E2E suite doubles as the
        # only automated check that a pure support login can work a ticket.
        SupportScope.objects.get_or_create(user=agent)

        self.stdout.write(self.style.SUCCESS(
            f"e2e accounts ready: {STUDENT_EMAIL} / {AGENT_EMAIL}"
        ))
