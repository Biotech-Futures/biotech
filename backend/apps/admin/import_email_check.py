"""Admin > Users > Import Students and Import Mentors: every address in the
file checked once it's chosen, before Import, as Add user's boxes are
(apps.admin.user_email_check).

``POST /api/v1/admin/user/import-check/`` ``{"kind": "students" | "mentors",
"rows": [{"row", "email", "firstName", "lastName", and a student's
"guardianEmail", "supervisorEmail", "supervisorFirstName",
"supervisorLastName"}], "lookup": bool}`` answers ``{"results": [{"row",
"problems": [message], "warnings": [{"field", "message"}]}], "lookups":
{"jobId", "status", "total", "done"} | null}``.

- A **problem** refuses the row, as importing does (add_users_by_role): not
  an address or the template's placeholder; an account already has the
  student's or mentor's; a student listed twice; a guardian who is the
  student or a student (an account, or one in the file); a supervisor who is
  the student, a student, or an account that isn't a supervisor's.
- A **warning** doesn't: a mailbox QuickEmailVerification says doesn't exist
  or couldn't check, an address that looks like a typo of its owner's name,
  a new supervisor's address a letter or two off an existing supervisor's,
  a guardian's address with an account.

With ``lookup``, each new address without an answer on file is looked up in
the background (email_precheck's job, ``GET .../import-check/<jobId>/``
follows it); asked again without it once that's done, the mailbox warnings
are there. Each address is paid for once: answers are kept
(QEV_RESULT_MAX_AGE_DAYS) and reused.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models.functions import Lower
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped
from apps.admin.user_email_check import (
    NOT_AN_EMAIL, SUPERVISOR_IS_STUDENT, SUPERVISOR_NOT_A_SUPERVISOR, SUPERVISOR_NOT_AN_EMAIL, TAKEN,
)
from apps.common.role_names import ROLE_STUDENT, ROLE_SUPERVISOR
from apps.resources.models import RoleAssignmentHistory
from apps.users.email_precheck import _client_tag, lookup_status, start_lookups
from apps.users.models import EmailVerification, StudentProfile, SupervisorProfile, User
from apps.users.serializers import (
    GUARDIAN_IS_SELF, GUARDIAN_IS_STUDENT, PLACEHOLDER_ADDRESS, SUPERVISOR_IS_SELF, _edit_distance,
    is_placeholder_email, name_email_warning, stored_email_answers,
)

MAX_ROWS = 5000
KINDS = ("students", "mentors")
GUARDIAN_NOT_AN_EMAIL = "Guardian email is not a valid email address"
WHOSE = {"email": None, "guardianEmail": "The guardian's", "supervisorEmail": "The supervisor's"}


class RowInput(serializers.Serializer):
    row = serializers.IntegerField(min_value=1)
    email = serializers.CharField(max_length=1000, allow_blank=True, trim_whitespace=False)
    firstName = serializers.CharField(max_length=255, allow_blank=True, default="")
    lastName = serializers.CharField(max_length=255, allow_blank=True, default="")
    guardianEmail = serializers.CharField(max_length=1000, allow_blank=True, default="")
    supervisorEmail = serializers.CharField(max_length=1000, allow_blank=True, default="")
    supervisorFirstName = serializers.CharField(max_length=255, allow_blank=True, default="")
    supervisorLastName = serializers.CharField(max_length=255, allow_blank=True, default="")


class CheckInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=KINDS)
    rows = serializers.ListField(child=RowInput(), min_length=1, max_length=MAX_ROWS)
    lookup = serializers.BooleanField(default=False)


def _is_email(address) -> bool:
    try:
        validate_email(address)
    except DjangoValidationError:
        return False
    return True


class Accounts:
    """The file's addresses that have an account, and which are a student's
    or a supervisor's (a profile, or that role ever), in a few queries."""

    def __init__(self, addresses):
        users = {}
        for user in User.objects.annotate(lowered=Lower("email")).filter(lowered__in=addresses).order_by("pk"):
            users.setdefault(user.lowered, user)
        ids = [user.pk for user in users.values()]
        self.users = users
        self.students = self._holding(StudentProfile, ROLE_STUDENT, ids)
        self.supervisors = self._holding(SupervisorProfile, ROLE_SUPERVISOR, ids)

    @staticmethod
    def _holding(profile_model, role_name, ids):
        return set(profile_model.objects.filter(user_id__in=ids).values_list("user_id", flat=True)) | set(
            RoleAssignmentHistory.objects.filter(user_id__in=ids, role__role_name__iexact=role_name)
            .values_list("user_id", flat=True)
        )

    def get(self, address):
        return self.users.get(address)

    def is_student(self, address) -> bool:
        user = self.users.get(address)
        return user is not None and user.pk in self.students

    def is_supervisor(self, address) -> bool:
        user = self.users.get(address)
        return user is not None and user.pk in self.supervisors


class Supervisors:
    """Every supervisor's address, to find one a new address is a letter or
    two off: the same domain with a near name, or the same name at a near
    domain (a typo in both at once is rare)."""

    def __init__(self):
        ids = set(SupervisorProfile.objects.values_list("user_id", flat=True)) | set(
            RoleAssignmentHistory.objects.filter(role__role_name__iexact=ROLE_SUPERVISOR)
            .values_list("user_id", flat=True)
        )
        self.by_domain, self.by_local = {}, {}
        for email, first, last in User.objects.filter(pk__in=ids).values_list("email", "first_name", "last_name"):
            local, _, domain = (email or "").strip().lower().rpartition("@")
            if local and domain:
                entry = (local, domain, f"{first or ''} {last or ''}".strip())
                self.by_domain.setdefault(domain, []).append(entry)
                self.by_local.setdefault(local, []).append(entry)

    @staticmethod
    def _near(a, b) -> bool:
        # One letter off a short part, up to two off a longer one.
        most = 1 if min(len(a), len(b)) < 6 else 2
        return abs(len(a) - len(b)) <= most and 1 <= _edit_distance(a, b) <= most

    def near(self, address):
        """(their address, their name) for the supervisor ``address`` is
        probably a typo of, or None."""
        local, _, domain = address.rpartition("@")
        for other_local, other_domain, name in self.by_domain.get(domain, ()):
            if self._near(local, other_local):
                return f"{other_local}@{other_domain}", name
        for other_local, other_domain, name in self.by_local.get(local, ()):
            if self._near(domain, other_domain):
                return f"{other_local}@{other_domain}", name
        return None


def _account_problem(email, accounts):
    if not email or not _is_email(email):
        return NOT_AN_EMAIL
    if is_placeholder_email(email):
        return PLACEHOLDER_ADDRESS
    return TAKEN if accounts.get(email) else None


def _guardian_problem(guardian, email, accounts, students_in_file):
    # ``students_in_file``: each student's address and its first row. The
    # student's own is caught as GUARDIAN_IS_SELF first.
    if not _is_email(guardian):
        return GUARDIAN_NOT_AN_EMAIL
    if is_placeholder_email(guardian):
        return PLACEHOLDER_ADDRESS
    if guardian == email:
        return GUARDIAN_IS_SELF
    if accounts.is_student(guardian):
        return GUARDIAN_IS_STUDENT
    if guardian in students_in_file:
        return f"The guardian's email is the student's in row {students_in_file[guardian]}."
    return None


def _supervisor_problem(supervisor, email, accounts, students_in_file):
    if not _is_email(supervisor):
        return SUPERVISOR_NOT_AN_EMAIL
    if is_placeholder_email(supervisor):
        return PLACEHOLDER_ADDRESS
    if supervisor == email:
        return SUPERVISOR_IS_SELF
    if accounts.is_student(supervisor):
        return SUPERVISOR_IS_STUDENT
    if accounts.get(supervisor) and not accounts.is_supervisor(supervisor):
        return SUPERVISOR_NOT_A_SUPERVISOR
    if supervisor in students_in_file:
        return f"The supervisor's email is the student's in row {students_in_file[supervisor]}."
    return None


def _mailbox(answers, address, whose):
    answer = answers.get(address)
    if answer is None:
        return None
    if answer.status == EmailVerification.Status.INVALID:
        suggestion = f" Did you mean {answer.did_you_mean}?" if answer.did_you_mean else ""
        return f"{whose} email doesn't appear to exist.{suggestion}"
    if answer.status == EmailVerification.Status.UNKNOWN:
        return f"{whose} email couldn't be verified."
    return None


def _clean(value) -> str:
    return (value or "").strip().lower()


def check_rows(kind, rows):
    """Each row's problems and warnings, and the addresses still to look up
    (those of rows without a problem that would get, or be, a new account's)."""
    who = "student" if kind == "students" else "mentor"
    owner = f"The {who}'s"
    emails = {field: [_clean(row[field]) for row in rows] for field in ("email", "guardianEmail", "supervisorEmail")}
    every = {address for column in emails.values() for address in column if address}
    accounts = Accounts(every)
    first_row = {}
    for row, email in zip(rows, emails["email"]):
        if email:
            first_row.setdefault(email, row["row"])
    supervisors = Supervisors() if kind == "students" and any(emails["supervisorEmail"]) else None

    checked, lookups = [], []
    for index, row in enumerate(rows):
        email = emails["email"][index]
        guardian = emails["guardianEmail"][index] if kind == "students" else ""
        supervisor = emails["supervisorEmail"][index] if kind == "students" else ""
        problems = [
            _account_problem(email, accounts),
            email and first_row[email] != row["row"] and f"This {who} is also in row {first_row[email]}.",
            # Neither can be a student, in an account or in the file.
            guardian and _guardian_problem(guardian, email, accounts, first_row),
            supervisor and _supervisor_problem(supervisor, email, accounts, first_row),
        ]
        problems = [problem for problem in problems if problem]
        new_supervisor = bool(supervisor) and accounts.get(supervisor) is None
        if not problems:
            lookups += [email, guardian, supervisor if new_supervisor else ""]
        checked.append((row, email, guardian, supervisor, new_supervisor, problems))

    addresses = list(dict.fromkeys(address for address in lookups if address))
    answers = stored_email_answers(addresses)
    results = []
    for row, email, guardian, supervisor, new_supervisor, problems in checked:
        warnings = []
        if not problems:
            warnings = [
                ("email", _mailbox(answers, email, owner)),
                ("email", name_email_warning(row["firstName"], row["lastName"], email)
                 and f"{owner} email looks like a typo of their name."),
                ("guardianEmail", guardian and _mailbox(answers, guardian, "The guardian's")),
                ("guardianEmail", guardian and accounts.get(guardian) and "The guardian's email already has an account."),
            ]
            if new_supervisor:
                near = supervisors.near(supervisor)
                warnings += [
                    ("supervisorEmail", _mailbox(answers, supervisor, "The supervisor's")),
                    ("supervisorEmail", name_email_warning(
                        row["supervisorFirstName"], row["supervisorLastName"], supervisor,
                    ) and "The supervisor's email looks like a typo of their name."),
                    ("supervisorEmail", near and (
                        f"The supervisor's email is a letter or two off {near[1] or 'a supervisor'}'s, "
                        f"{near[0]}. Did you mean that? Importing makes a new supervisor account for this one."
                    )),
                ]
        results.append({
            "row": row["row"], "problems": problems,
            "warnings": [{"field": field, "message": message} for field, message in warnings if message],
        })
    return results, addresses


class ImportEmailCheckView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_import_email_check"

    def post(self, request):
        parser = CheckInput(data=request.data)
        parser.is_valid(raise_exception=True)
        data = parser.validated_data
        results, addresses = check_rows(data["kind"], data["rows"])
        lookups = None
        if data["lookup"] and addresses:
            lookups = start_lookups(addresses, tag=_client_tag(request), user=request.user)
            if lookups["status"] != "started":
                # Every answer was on file already: these results have them.
                lookups = None
        return Response({"results": results, "lookups": lookups})


class ImportEmailCheckStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, job_id):
        body, code = lookup_status(job_id)
        return Response(body, status=code)
