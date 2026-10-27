"""Admin > Users > Add user (and Edit): its email boxes checked as each is
left (``POST /api/v1/admin/user/email-check/``), as a registration page's are
(apps.users.email_field_check), with the same messages.

Request: ``{"fields": [{"field", "kind", "email", "firstName"?, "lastName"?,
"accountEmail"?, "userId"?, "school"?}]}`` with at most MAX_FIELDS fields.
``kind`` is account (the user's own address), guardian (a student's
guardian's; ``accountEmail`` is the student's), or school (a student's School,
in ``school``: a warning when it looks like a university, as registering's). ``userId`` is the user being edited, whose
own address isn't "already used".

Answer, always 200: ``{"results": {<field>: {"ok": true}, or {"ok": false,
"severity": "hard", "code", "message"}, or {"ok": false, "severity": "soft",
"warnings": [{"code", "message"}]}}}``.

- Hard, which saving refuses too (create_user): not an email address, the
  template's placeholder, an address another account has, a guardian who is
  the student, or a current student's address as a guardian.
- Soft, only shown under the box (saving goes ahead): a mailbox
  QuickEmailVerification says doesn't exist or couldn't check, a name that
  looks like a typo of the address, a guardian address that has an account, a
  School that looks like a university.

Each new address is looked up once and the answer kept, as registration's
are (verify_email), so at most ``admin_user_email_check`` requests a minute.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped
from apps.users import email_verification
from apps.common.role_names import ROLE_STUDENT, ROLE_SUPERVISOR
from apps.users.models import StudentProfile, SupervisorProfile, User
from apps.users.serializers import (
    GUARDIAN_IS_SELF, PLACEHOLDER_ADDRESS, SUPERVISOR_IS_SELF, _has_role, guardian_account_warning,
    is_placeholder_email, mailbox_warning, name_email_warning, new_guardian_email_problem, school_warning,
)

MAX_FIELDS = 10
KINDS = ("account", "guardian", "school")
NOT_AN_EMAIL = "Enter a valid email address."
TAKEN = "Account email already exists"
SUPERVISOR_NOT_AN_EMAIL = "Supervisor email is not a valid email address"
SUPERVISOR_IS_STUDENT = "The supervisor's email belongs to a student, so they can't be a supervisor."
SUPERVISOR_NOT_A_SUPERVISOR = "The supervisor's email belongs to an account that isn't a supervisor's."


class FieldInput(serializers.Serializer):
    field = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(choices=KINDS)
    email = serializers.CharField(max_length=1000, allow_blank=True, trim_whitespace=False)
    firstName = serializers.CharField(max_length=255, allow_blank=True, default="")
    lastName = serializers.CharField(max_length=255, allow_blank=True, default="")
    accountEmail = serializers.CharField(max_length=1000, allow_blank=True, default="")
    userId = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    school = serializers.CharField(max_length=255, allow_blank=True, default="")


class CheckInput(serializers.Serializer):
    fields = serializers.ListField(child=FieldInput(), min_length=1, max_length=MAX_FIELDS)


def account_email_problem(email, *, user_id=None) -> str | None:
    """Why an account can't have ``email``: refused at Add user and here."""
    try:
        validate_email(email)
    except DjangoValidationError:
        return NOT_AN_EMAIL
    if is_placeholder_email(email):
        return PLACEHOLDER_ADDRESS
    taken = User.objects.filter(email__iexact=email)
    if user_id:
        taken = taken.exclude(pk=user_id)
    return TAKEN if taken.exists() else None


def guardian_email_problem(email, account_email) -> str | None:
    """Why a student's guardian can't have ``email``: refused at Add user and here."""
    try:
        validate_email(email)
    except DjangoValidationError:
        return "Guardian email is not a valid email address"
    if is_placeholder_email(email):
        return PLACEHOLDER_ADDRESS
    if email == (account_email or "").strip().lower():
        return GUARDIAN_IS_SELF
    return new_guardian_email_problem(email)


def supervisor_email_problem(email, student_email) -> str | None:
    """Why an imported student's supervisor can't have ``email``: as
    registering refuses, so no student, mentor or admin is made one."""
    if not email or not _is_email(email):
        return SUPERVISOR_NOT_AN_EMAIL
    if is_placeholder_email(email):
        return PLACEHOLDER_ADDRESS
    if email == (student_email or "").strip().lower():
        return SUPERVISOR_IS_SELF
    existing = User.objects.by_email(email)
    if existing is None:
        return None
    if _has_role(existing, StudentProfile, ROLE_STUDENT):
        return SUPERVISOR_IS_STUDENT
    if not _has_role(existing, SupervisorProfile, ROLE_SUPERVISOR):
        return SUPERVISOR_NOT_A_SUPERVISOR
    return None


def _is_email(address) -> bool:
    try:
        validate_email(address)
    except DjangoValidationError:
        return False
    return True


def _check(item, answers):
    if item["kind"] == "school":
        warning = school_warning(item["school"]) if item["school"].strip() else None
        return (
            {"ok": False, "severity": "soft", "warnings": [{"code": warning["code"], "message": warning["message"]}]}
            if warning else {"ok": True}
        )
    email = item["email"].strip().lower()
    if not email:
        return {"ok": True}
    if item["kind"] == "account":
        problem = account_email_problem(email, user_id=item["userId"])
    else:
        problem = guardian_email_problem(email, item["accountEmail"])
    if problem:
        return {"ok": False, "severity": "hard", "code": "email_refused", "message": problem}
    with email_verification.lookups_for("admin_box_check"):
        answers[email] = email_verification.verify_email(email)
    if item["kind"] == "account":
        found = [
            mailbox_warning(answers, email, "Title"),
            name_email_warning(item["firstName"], item["lastName"], email, "the user's"),
        ]
    else:
        found = [mailbox_warning(answers, email, "GuardianEmail"), guardian_account_warning(email)]
    warnings = [{"code": w["code"], "message": w["message"]} for w in found if w]
    return {"ok": False, "severity": "soft", "warnings": warnings} if warnings else {"ok": True}


def check_fields(fields) -> dict:
    answers = {}
    return {item["field"]: _check(item, answers) for item in fields}


class UserEmailCheckView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_user_email_check"

    def post(self, request):
        parser = CheckInput(data=request.data)
        parser.is_valid(raise_exception=True)
        return Response({"results": check_fields(parser.validated_data["fields"])})
