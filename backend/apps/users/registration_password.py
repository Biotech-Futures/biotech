"""Setting a password straight after registering. A student, mentor or
supervisor who registers themselves gets, with their receipt, a token for
their account (``passwordToken``); the page they're taken to next sends it
back with the password they choose.

- ``POST /api/v1/registration/password/`` ``{token, password}``: sets the
  account's first password, as the first-sign-in page does
  (``SetPasswordView``), and signs them in, answering ``{signedIn, user,
  csrfToken}``. A mentor isn't signed in (``signedIn: false``): their account
  waits for an admin to activate it.

A token is for one account, for an hour, and only while it has no password:
once one is set, it's the reset link's to change. It's given only for
someone registering themselves, never for students a supervisor or admin
registers.
"""
from __future__ import annotations

import logging

from django.contrib.auth import login
from django.core import signing
from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pii import email_log_tag

from .models import RegistrationSubmission, User

logger = logging.getLogger(__name__)

SALT = "registration-password"
MAX_AGE_SECONDS = 60 * 60
# Who registers themselves: the person who sent the form is the receipt's
# account (a group's creator, or one joining it).
SELF_JOURNEYS = {"student_individual", "student_team", "mentor", "supervisor"}
EXPIRED = "This link to set your password has expired. Sign in with your email to set one."


def password_token(user) -> str:
    return signing.TimestampSigner(salt=SALT).sign(str(user.pk))


def with_password_token(data):
    """A self-registration's receipt, with the token for its account while it
    has no password. Anything else unchanged."""
    if not isinstance(data, dict) or data.get("journey") not in SELF_JOURNEYS or not data.get("reference_code"):
        return data
    submission = (
        RegistrationSubmission.objects.select_related("student").filter(reference=data["reference_code"]).first()
    )
    if submission is None or submission.student.has_usable_password():
        return data
    return {**data, "passwordToken": password_token(submission.student)}


class RegistrationPasswordView(APIView):
    """Set a new registration's first password (see the module)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.data.get("token") or ""
        password = request.data.get("password") or ""
        try:
            user_id = signing.TimestampSigner(salt=SALT).unsign(str(token), max_age=MAX_AGE_SECONDS)
        except signing.BadSignature:
            raise serializers.ValidationError({"detail": EXPIRED})
        user = User.objects.filter(pk=user_id).first()
        if user is None or user.account_status in User.INACTIVE_LOGIN_STATUSES:
            raise serializers.ValidationError({"detail": EXPIRED})
        if user.has_usable_password():
            raise serializers.ValidationError({"detail": "Your password is already set. Sign in with it."})
        # As the first-sign-in page asks (SetPasswordView).
        if len(password) < 8:
            raise serializers.ValidationError({"password": ["Password must be at least 8 characters."]})
        user.set_password(password)
        user.save(update_fields=["password"])
        logger.info("registration_password: set email_tag=%s", email_log_tag(user.email))
        if not user.is_active:
            # A mentor, until an admin activates them.
            return Response({"signedIn": False})
        user.backend = "apps.users.backends.CachedModelBackend"
        login(request, user)
        return Response({
            "signedIn": True,
            "user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name},
            # login() rotates the CSRF token; the page carries on with the new one.
            "csrfToken": get_token(request),
        })
