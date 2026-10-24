"""Setting a password straight after registering. A student, mentor or
supervisor who registers themselves gets, with their receipt, a token for
their account (``passwordToken``); the page they're taken to next sends it
back with the password they choose. A student someone else registers (a
teammate, their supervisor or an admin) is emailed a link with one instead
(``emailed_password_url``), in their registration email.

- ``GET /api/v1/registration/password/?token=``: whether the page asks for
  their parent or guardian too, ``{needsGuardian, guardian, needsPolicies}``
  (``guardian``: what's on file). A student registered without all their
  guardian's details gives them with their password, as at first sign-in;
  and someone registered by others agrees to the policies
  (``needs_policies``).
- ``POST /api/v1/registration/password/`` ``{token, password, guardian?,
  policiesAgreed?}``: checks the policies are agreed to when asked, saves the
  guardian if they're asked for (``save_own_guardian``: emailed the consent
  form), then sets the account's first password (and when they agreed), as the
  first-sign-in page does (``SetPasswordView``), and signs them in, answering
  ``{signedIn, user, csrfToken}``. An account that isn't active isn't
  signed in (``signedIn: false``).

A token is for one account, and only while it has no password: once one is
set, it's the reset link's to change. A receipt's lasts an hour from
registering. It's signed with when the registration was saved, so an
unchanged retry's receipt is the same receipt, token and all. It's given only
for someone registering themselves. An emailed one lasts 14 days from when it
was sent, and is signed apart (``EMAIL_SALT``), so a receipt's can't be made
to last as long.
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login
from django.core import signing
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pii import email_log_tag
from apps.common.rbac import is_admin, user_has_role
from apps.common.role_names import ROLE_MENTOR, ROLE_STUDENT, ROLE_SUPERVISOR

from .models import RegistrationSubmission, StudentProfile, User

logger = logging.getLogger(__name__)

SALT = "registration-password"
MAX_AGE_SECONDS = 60 * 60
EMAIL_SALT = "registration-password-email"
EMAIL_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
# Who registers themselves: the person who sent the form is the receipt's
# account (a group's creator, or one joining it).
SELF_JOURNEYS = {"student_individual", "student_team", "mentor", "supervisor"}
EXPIRED = "This link to set your password has expired. Sign in with your email to set one."
PAGE_PATH = "/#/register/password"
POLICIES_NEEDED = "Agree to the BIOTech Futures policies to continue."


def needs_policies(user) -> bool:
    """A student, mentor or supervisor who hasn't agreed to the BIOTech
    Futures policies: someone registered by a teammate, their supervisor or an
    admin, as the form asks only the person filling it in. They agree on the
    Set password page, from their email's link or at first sign-in
    (SetPasswordView). Never an admin or a support agent."""
    if user.policies_agreed_at is not None or is_admin(user):
        return False
    return user_has_role(user, ROLE_STUDENT, ROLE_MENTOR, ROLE_SUPERVISOR)


def require_policies_agreed(user, data) -> bool:
    """Raises unless someone who needs to has agreed to the policies (data's
    ``policiesAgreed``); whether to record that they have."""
    needed = needs_policies(user)
    if needed and data.get("policiesAgreed") is not True:
        raise serializers.ValidationError({"policiesAgreed": [POLICIES_NEEDED]})
    return needed


class _RegisteredAtSigner(signing.TimestampSigner):
    """Signs with when the registration was saved, not now."""

    def __init__(self, registered_at):
        super().__init__(salt=SALT)
        self.registered_at = registered_at

    def timestamp(self):
        return signing.b62_encode(int(self.registered_at.timestamp()))


def password_token(user, registered_at) -> str:
    return _RegisteredAtSigner(registered_at).sign(str(user.pk))


def emailed_password_url(user) -> str:
    """The Set password page's link, for 14 days, that a student someone else
    registered is emailed (registration_emails)."""
    token = signing.TimestampSigner(salt=EMAIL_SALT).sign(str(user.pk))
    return f"{settings.FRONTEND_BASE_URL}{PAGE_PATH}?{urlencode({'token': token})}"


def sample_password_url() -> str:
    """A link that sets no one's password, for System Emails' previews and
    test sends."""
    return f"{settings.FRONTEND_BASE_URL}{PAGE_PATH}?{urlencode({'token': 'sample'})}"


def _account(token) -> User:
    """The account a receipt's or an emailed token is for, while it can still
    sign in; else the token's refused as expired."""
    for salt, max_age in ((SALT, MAX_AGE_SECONDS), (EMAIL_SALT, EMAIL_MAX_AGE_SECONDS)):
        try:
            user_id = signing.TimestampSigner(salt=salt).unsign(str(token or ""), max_age=max_age)
        except signing.BadSignature:
            continue
        user = User.objects.filter(pk=user_id).first()
        if user is not None and user.account_status not in User.INACTIVE_LOGIN_STATUSES:
            return user
        break
    raise serializers.ValidationError({"detail": EXPIRED})


def _unset(user) -> None:
    if user.has_usable_password():
        raise serializers.ValidationError({"detail": "Your password is already set. Sign in with it."})


def _guardian_on_file(user) -> dict | None:
    """A student's guardian as their profile has it, while any of it is
    missing; None for anyone else, or a student with all of it."""
    if not user_has_role(user, ROLE_STUDENT):
        return None
    profile = StudentProfile.objects.filter(user=user).first()
    if profile is None:
        return None
    guardian = {
        "first_name": (profile.pg_first_name or "").strip(),
        "last_name": (profile.pg_last_name or "").strip(),
        "email": (profile.pg_email or "").strip(),
    }
    return None if all(guardian.values()) else guardian


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
    return {**data, "passwordToken": password_token(submission.student, submission.created_at)}


class RegistrationPasswordView(APIView):
    """Set a new registration's first password (see the module)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        user = _account(request.query_params.get("token"))
        _unset(user)
        guardian = _guardian_on_file(user)
        return Response({
            "needsGuardian": guardian is not None, "guardian": guardian, "needsPolicies": needs_policies(user),
        })

    def post(self, request):
        password = request.data.get("password") or ""
        user = _account(request.data.get("token"))
        _unset(user)
        # As the first-sign-in page asks (SetPasswordView).
        if len(password) < 8:
            raise serializers.ValidationError({"password": ["Password must be at least 8 characters."]})
        agreeing = require_policies_agreed(user, request.data)
        # Their guardian first, as at first sign-in: refused, no password is set.
        if _guardian_on_file(user) is not None:
            from .views import save_own_guardian

            guardian = request.data.get("guardian")
            save_own_guardian(user, guardian if isinstance(guardian, dict) else {})
        user.set_password(password)
        fields = ["password"]
        if agreeing:
            user.policies_agreed_at = timezone.now()
            fields.append("policies_agreed_at")
        user.save(update_fields=fields)
        logger.info("registration_password: set email_tag=%s", email_log_tag(user.email))
        if not user.is_active:
            # Not active (an admin's to activate): signed in once they are.
            return Response({"signedIn": False})
        user.backend = "apps.users.backends.CachedModelBackend"
        login(request, user)
        return Response({
            "signedIn": True,
            "user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name},
            # login() rotates the CSRF token; the page carries on with the new one.
            "csrfToken": get_token(request),
        })
