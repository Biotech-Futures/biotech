"""Accounts the ticket E2E suite logs in with. Idempotent, dev-only.

The E2E tests drive real login forms, so they need real accounts with
known passwords. Rerunning always resets those passwords: a rehearsal
database that drifted (someone changed a password by hand) heals instead
of failing the whole suite at the login step.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.admin.services.user import resolve_role_id
from apps.resources.models import RoleAssignmentHistory
from apps.tickets.models import SupportScope
from apps.users.models.admin_scope import AdminScope

STUDENT_EMAIL = "e2e.student@example.com"
AGENT_EMAIL = "e2e.agent@example.com"
# Not secrets: these exist only in DEBUG databases, and the E2E specs
# hard-code them on the other side of the login form.
STUDENT_PASSWORD = "E2eStudent1!"
AGENT_PASSWORD = "E2eAgent1!"
SUPPORT_ROLE = "support"


# Databases this command will write to without being forced. DEBUG alone is
# not enough of a guard: a developer's DEBUG environment normally points at
# the database they do their real work in, and this command overwrites
# passwords with published ones.
_SCRATCH_DB_MARKERS = ("rehearsal", "test", "e2e", "scratch")


def _active_assignment(user):
    """The role assignment the platform treats as current.

    The same question apps/users/serializers.UserSerializer._active_assignment
    asks, so "already support" here means what /users/me/ will report.
    """
    now = timezone.now()
    return (
        RoleAssignmentHistory.objects.select_related("role")
        .filter(user=user, valid_from__lte=now)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        .order_by("-valid_from")
        .first()
    )


def _ensure_support_role(user) -> bool:
    """Give ``user`` the role "support", the way the admin user service does.

    Returns whether anything was written. A rerun on an account that already
    holds the role writes nothing, so the command stays idempotent: no second
    assignment row, no second Roles row. An account holding some other role is
    moved the way apps/admin/services/user.update_user moves one: the open
    assignment is closed and a new one opened, so the history still says what
    it was before. resolve_role_id is that service's own lookup (a
    case-insensitive get_or_create), so an existing "Support" row is reused
    rather than duplicated.
    """
    current = _active_assignment(user)
    if current is not None and current.role is not None:
        if (current.role.role_name or "").strip().lower() == SUPPORT_ROLE:
            return False

    now = timezone.now()
    role_id = resolve_role_id(SUPPORT_ROLE)
    RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).update(valid_to=now)
    RoleAssignmentHistory.objects.create(
        user=user, role_id=role_id, valid_from=now, valid_to=None
    )
    return True


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
        # Not staff: the portal reads is_staff as "admin" whatever the role
        # says (stores/auth.ts resolveNormalizedRole), and the admin user
        # service sets both flags from the role in the same way.
        agent.is_staff = False
        agent.is_superuser = False
        agent.save()
        agent.activate()
        # Support-capable but NOT an admin: the E2E suite doubles as the
        # only automated check that a pure support login can work a ticket.
        #
        # Queue access alone is not what the People page makes. An agent
        # created there also carries the role "support", and the portal goes
        # by the role to decide who the account is: without it this account
        # read as a student, landed on the student dashboard and was offered
        # the member pages, so the suite was testing a combination the
        # product never creates.
        with transaction.atomic():
            SupportScope.objects.get_or_create(user=agent)
            _ensure_support_role(agent)
            # The user service drops the admin marker whenever the role is not
            # admin. Done here too so a drifted database cannot turn the pure
            # agent into an admin behind the suite's back.
            AdminScope.objects.filter(user=agent).delete()

        self.stdout.write(self.style.SUCCESS(
            f"e2e accounts ready: {STUDENT_EMAIL} / {AGENT_EMAIL}"
        ))
