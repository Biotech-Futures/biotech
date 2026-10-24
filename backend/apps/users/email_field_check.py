"""Checking a registration page's boxes as each is left, and when its
Continue is pressed (``POST /api/v1/registration/email-check/field/``), with
what Submit would refuse (hard) or warn about (soft). At most
``registration_email_field_check`` requests a minute from one person.

Request: ``{"journey"?, "fields": [{"field", "kind", "email", "studentEmail"?,
"student"?, "firstName"?, "lastName"?, "school"?, "overrides"?}]}`` with at
most MAX_FIELDS fields. ``kind`` is student, guardian, supervisor (the one a
student names), mentor, supervisor_self (a supervisor registering
themselves) or school (the student's school, from ``school``; no ``email``).
``student`` is the
student's place in the registration (0 when not given), for override paths;
``overrides`` are those already ticked, as at Submit.

Answer, always 200: ``{"results": {<field>: {"ok": true}, or {"ok": false,
"severity": "hard", "code", "message"}, or {"ok": false, "severity": "soft",
"warnings": [{"code", "message", "field", "override_field"}]}}}``. Each kind runs
Submit's own checks in order and stops at the first hard problem; the mailbox
is a fresh answer on file, or one lookup that's stored for Submit (within
QEV_DAILY_LOOKUP_CAP). While any field has a hard problem, no soft one is
given, as at Submit. A field gets at most one warning: the mailbox's first.
"""
from __future__ import annotations

from rest_framework import permissions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import email_verification
from .mentor_registration import (
    JOURNEY as MENTOR_JOURNEY, MENTOR_EMAIL_TAKEN, MENTOR_NAME, mentor_email_taken,
)
from .registration_intake import STUDENT_JOURNEYS, StrictInput, current_window, error_fields, registration_field
from .serializers import (
    GUARDIAN_IS_SELF, MAILBOX_WHOSE, REGISTRATION_OVERRIDES, SUPERVISOR_IS_SELF, UNKNOWN_OVERRIDE,
    StrictBooleanField, UserRegisterBodySerializer, guardian_account_warning, mailbox_warning, name_email_warning,
    refuse_invalid_mailbox, refuse_placeholder, school_warning, supervisor_name_email_warning,
)
from .supervisor_registration import (
    JOURNEY as SUPERVISOR_JOURNEY, SUPERVISOR_EMAIL_TAKEN, SUPERVISOR_NAME, supervisor_email_taken,
)

MAX_FIELDS = 50
# ``supervisor`` is the supervisor a student names; ``supervisor_self`` a
# supervisor registering themselves, checked as Submit checks them
# (supervisor_registration).
KINDS = {
    "student": "Title", "guardian": "GuardianEmail", "supervisor": "SupervisorEmail", "mentor": "Title",
    "supervisor_self": "Title",
}
# Those registering themselves alone: their own email, and their own name.
OWN = {
    "mentor": ("mentor", MENTOR_NAME),
    "supervisor_self": ("supervisor", SUPERVISOR_NAME),
}
SAME_AS_STUDENT = {
    "guardian": (GUARDIAN_IS_SELF, "guardian_same_as_student"),
    "supervisor": (SUPERVISOR_IS_SELF, "supervisor_same_as_student"),
}


class Lookups:
    """Each address's answer, looked up the first time it's asked for."""

    def __init__(self):
        self.answers = {}

    def get(self, address):
        if not address:
            return None
        if address not in self.answers:
            self.answers[address] = email_verification.verify_email(address)
        return self.answers[address]


class FieldInput(StrictInput):
    field = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(choices=sorted([*KINDS, "school"]))
    email = serializers.CharField(max_length=1000, allow_blank=True, trim_whitespace=False, required=False)
    studentEmail = serializers.CharField(max_length=1000, allow_blank=True, default="")
    student = serializers.IntegerField(min_value=0, max_value=MAX_FIELDS, default=0)
    firstName = serializers.CharField(max_length=255, allow_blank=True, default="")
    lastName = serializers.CharField(max_length=255, allow_blank=True, default="")
    school = serializers.CharField(max_length=255, allow_blank=True, default="")
    overrides = serializers.DictField(child=StrictBooleanField(), default=dict)

    def validate_overrides(self, value):
        if set(value) - REGISTRATION_OVERRIDES:
            raise serializers.ValidationError(UNKNOWN_OVERRIDE)
        return value

    def validate(self, data):
        if data["kind"] != "school" and "email" not in data:
            raise serializers.ValidationError({"email": [self.fields["email"].error_messages["required"]]})
        data.setdefault("email", "")
        return data


class FieldCheckInput(StrictInput):
    journey = serializers.ChoiceField(choices=[*STUDENT_JOURNEYS, MENTOR_JOURNEY, SUPERVISOR_JOURNEY], required=False)
    fields = serializers.ListField(child=FieldInput(), min_length=1, max_length=MAX_FIELDS)

    def validate_fields(self, value):
        paths = [item["field"] for item in value]
        if len(set(paths)) < len(paths):
            raise serializers.ValidationError("Each field may be checked once per request.")
        return value


def _check(kind, email, student_email, answers):
    """The first thing Submit would refuse about ``email`` as ``kind``: a
    ValidationError raised, nothing for none."""
    if kind == "school" or (kind in SAME_AS_STUDENT and not email.strip()):
        return
    validator = UserRegisterBodySerializer(
        context={"email_answers": answers, "invalid_is_error": True, "check_supervisor": True},
    )
    name = KINDS[kind]
    value = validator.fields[name].run_validation(email)
    if kind == "mentor":
        refuse_placeholder(value)
        if mentor_email_taken(value, current_window()):
            raise serializers.ValidationError(MENTOR_EMAIL_TAKEN, code="email_taken")
        refuse_invalid_mailbox(answers, value, MAILBOX_WHOSE[name])
        return
    if kind == "supervisor_self":
        refuse_placeholder(value)
        if supervisor_email_taken(value):
            raise serializers.ValidationError(SUPERVISOR_EMAIL_TAKEN, code="email_taken")
        refuse_invalid_mailbox(answers, value, MAILBOX_WHOSE[name])
        return
    if kind in SAME_AS_STUDENT:
        refuse_placeholder(value)
        if value.strip().lower() == student_email.strip().lower():
            message, code = SAME_AS_STUDENT[kind]
            raise serializers.ValidationError(message, code=code)
    getattr(validator, f"validate_{name}")(value)


def _warning(item, answers):
    """The field's first soft warning not already confirmed, with Submit's paths."""
    kind, email = item["kind"], item["email"].strip()
    named = bool(item["firstName"].strip() or item["lastName"].strip())
    if kind == "school":
        found = [school_warning(item["school"])]
    elif not email:
        found = []
    elif kind == "guardian":
        found = [
            mailbox_warning(answers, email, "GuardianEmail", invalid_is_error=True),
            guardian_account_warning(email),
        ]
    elif kind == "supervisor":
        found = [
            mailbox_warning(answers, email, "SupervisorEmail", invalid_is_error=True),
            named and supervisor_name_email_warning(item["firstName"], item["lastName"], email),
        ]
    else:
        whose = OWN[kind][1] if kind in OWN else "the student's"
        found = [
            mailbox_warning(answers, email, "Title", invalid_is_error=True),
            named and name_email_warning(item["firstName"], item["lastName"], email, whose),
        ]
    warning = next((w for w in found if w and not item["overrides"].get(w["override_field"])), None)
    if warning is None:
        return None
    if kind in OWN:
        prefix = OWN[kind][0]
        return {
            **warning, "field": f"{prefix}.email", "override_field": f"{prefix}.overrides.{warning['override_field']}",
        }
    index = 0 if kind == "supervisor" else item["student"]
    return {
        **warning, "field": registration_field(warning["field"], item["student"]),
        "override_field": f"students.{index}.overrides.{warning['override_field']}",
    }


def check_fields(fields) -> dict:
    answers = Lookups()
    results = {}
    for item in fields:
        try:
            _check(item["kind"], item["email"], item["studentEmail"], answers)
        except serializers.ValidationError as error:
            detail = error.detail[0] if isinstance(error.detail, list) else error.detail
            results[item["field"]] = {"ok": False, "severity": "hard", "code": detail.code, "message": str(detail)}
        else:
            results[item["field"]] = {"ok": True}
    if any(not result["ok"] for result in results.values()):
        return results
    for item in fields:
        warning = _warning(item, answers)
        if warning:
            results[item["field"]] = {"ok": False, "severity": "soft", "warnings": [warning]}
    return results


class EmailFieldCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]
    # A page checks each box as it's left, and each new address can cost a
    # QuickEmailVerification lookup: a limit per person (IP, or account when
    # signed in) keeps a script from spending them. Past it, 429; Submit
    # still checks.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration_email_field_check"

    def post(self, request):
        parser = FieldCheckInput(data=request.data)
        if not parser.is_valid():
            raise serializers.ValidationError(error_fields(parser.errors))
        return Response({"results": check_fields(parser.validated_data["fields"])})
