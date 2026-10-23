"""Checking a registration's email boxes as the person leaves each one
(``POST /api/v1/registration/email-check/field/``), so the page can show a
problem under the box before Continue. Only what Submit would refuse is
reported, never what it only warns about.

Request: ``{"journey"?, "fields": [{"field", "kind", "email", "studentEmail"?}]}``
with at most MAX_FIELDS fields; ``kind`` is student, guardian, supervisor or
mentor. Answer, always 200: ``{"results": {<field>: {"ok": true} or
{"ok": false, "code", "message"}}}``. Each kind runs Submit's own checks in
order and stops at the first problem. The last is the mailbox: a fresh answer
on file, or one lookup that's stored for Submit (within QEV_DAILY_LOOKUP_CAP).
"""
from __future__ import annotations

from rest_framework import permissions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import email_verification
from .mentor_registration import JOURNEY as MENTOR_JOURNEY, MENTOR_EMAIL_TAKEN, mentor_email_taken
from .registration_intake import STUDENT_JOURNEYS, StrictInput, current_window, error_fields
from .serializers import (
    GUARDIAN_IS_SELF, MAILBOX_WHOSE, SUPERVISOR_IS_SELF, UserRegisterBodySerializer, refuse_invalid_mailbox,
    refuse_placeholder,
)

MAX_FIELDS = 50
KINDS = {"student": "Title", "guardian": "GuardianEmail", "supervisor": "SupervisorEmail", "mentor": "Title"}
SAME_AS_STUDENT = {
    "guardian": (GUARDIAN_IS_SELF, "guardian_same_as_student"),
    "supervisor": (SUPERVISOR_IS_SELF, "supervisor_same_as_student"),
}


class Lookups:
    """Each address's answer, looked up the first time it's asked for."""

    def __init__(self):
        self.answers = {}

    def get(self, address):
        if address not in self.answers:
            self.answers[address] = email_verification.verify_email(address)
        return self.answers[address]


class FieldInput(StrictInput):
    field = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(choices=sorted(KINDS))
    email = serializers.CharField(max_length=1000, allow_blank=True, trim_whitespace=False)
    studentEmail = serializers.CharField(max_length=1000, allow_blank=True, default="")


class FieldCheckInput(StrictInput):
    journey = serializers.ChoiceField(choices=[*STUDENT_JOURNEYS, MENTOR_JOURNEY], required=False)
    fields = serializers.ListField(child=FieldInput(), min_length=1, max_length=MAX_FIELDS)

    def validate_fields(self, value):
        paths = [item["field"] for item in value]
        if len(set(paths)) < len(paths):
            raise serializers.ValidationError("Each field may be checked once per request.")
        return value


def _check(kind, email, student_email, answers):
    """The first thing Submit would refuse about ``email`` as ``kind``: a
    ValidationError raised, nothing for none."""
    if kind in SAME_AS_STUDENT and not email.strip():
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
    if kind in SAME_AS_STUDENT:
        refuse_placeholder(value)
        if value.strip().lower() == student_email.strip().lower():
            message, code = SAME_AS_STUDENT[kind]
            raise serializers.ValidationError(message, code=code)
    getattr(validator, f"validate_{name}")(value)


def check_fields(fields) -> dict:
    answers = Lookups()
    results = {}
    for item in fields:
        try:
            _check(item["kind"], item["email"], item["studentEmail"], answers)
        except serializers.ValidationError as error:
            detail = error.detail[0] if isinstance(error.detail, list) else error.detail
            results[item["field"]] = {"ok": False, "code": detail.code, "message": str(detail)}
        else:
            results[item["field"]] = {"ok": True}
    return results


class EmailFieldCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]

    def post(self, request):
        parser = FieldCheckInput(data=request.data)
        if not parser.is_valid():
            raise serializers.ValidationError(error_fields(parser.errors))
        return Response({"results": check_fields(parser.validated_data["fields"])})
