"""A supervisor back for a new year, on the registration page. Start new
year deactivated their account, and supervisors don't register themselves,
so they confirm their email with a sign-in code instead: that reactivates the
account and signs them in, to register their students as before. Open only
while registration is (Management > Registration). Asked for and checked as
the sign-in page's code is, with the same limits.

- ``POST /api/v1/registration/returning-supervisor/`` ``{email}``: emails the
  code to a supervisor's address; 200 with the same answer for any address.
- ``POST /api/v1/registration/returning-supervisor/confirm/`` ``{email,
  code}``: reactivates and signs them in, answering as the sign-in page's
  code check does (``user``, ``csrfToken``).
"""
from __future__ import annotations

import logging

from django.contrib.auth import login
from django.core.cache import cache
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.common.pii import email_log_tag
from apps.common.rbac import user_has_role
from apps.common.role_names import ROLE_SUPERVISOR, get_role_by_name
from apps.resources.models import RoleAssignmentHistory
from apps.services import auth_service
from apps.services.views import (
    LOGIN_SEND_MIN_INTERVAL_SECONDS,
    OTP_ATTEMPT_LIMIT,
    OTP_ATTEMPT_WINDOW_SECONDS,
    OTP_IP_ATTEMPT_MULTIPLIER,
    _bump_login_send_counters,
    _check_login_send_throttle,
    _claim_min_interval,
    _client_ip,
    _login_send_cooldown_key,
)
from config.errors import (
    EmailAndCodeRequired,
    EmailRequired,
    InvalidOrExpiredCode,
    LoginSendRateLimited,
    TooManyFailedAttempts,
)

from .models import User
from .registration_intake import current_window
from .returning import returning_supervisor

logger = logging.getLogger(__name__)

SENT = "If that's a supervisor's email, we've emailed it a code."


class RegistrationClosed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Registration is closed, so supervisors can't come back to register students now."
    default_code = "registration_closed"


def _require_open() -> None:
    if not current_window().is_open(timezone.now()):
        raise RegistrationClosed()


class ReturningSupervisorCodeView(APIView):
    """Email a supervisor the code that brings them back (see the module)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            raise EmailRequired()
        _require_open()
        ip = _client_ip(request)
        _check_login_send_throttle(email, ip)
        retry_after = _claim_min_interval(_login_send_cooldown_key(email), LOGIN_SEND_MIN_INTERVAL_SECONDS)
        if retry_after:
            raise LoginSendRateLimited(retry_after=retry_after)
        _bump_login_send_counters(email, ip)
        # Only a supervisor's address is emailed; every address gets the same
        # answer, so the page can't be used to find out whose is whose.
        if returning_supervisor(email) is not None:
            auth_service.send_login_code(email)
        return Response({"message": SENT})


class ReturningSupervisorConfirmView(APIView):
    """Check the code, reactivate the supervisor and sign them in (see the module)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        code = request.data.get("code")
        if not email or not code:
            raise EmailAndCodeRequired()
        _require_open()

        # Counted with the sign-in page's tries, so neither gives more.
        ip = _client_ip(request)
        cache_key = f"otp_attempts:{email}"
        ip_key = f"otp_attempts_ip:{ip}"
        attempts = cache.get(cache_key, 0)
        ip_attempts = cache.get(ip_key, 0)
        if attempts >= OTP_ATTEMPT_LIMIT or ip_attempts >= OTP_ATTEMPT_LIMIT * OTP_IP_ATTEMPT_MULTIPLIER:
            raise TooManyFailedAttempts()

        user = returning_supervisor(email)
        if user is None or not auth_service.verify_login_code(email, code):
            cache.set(cache_key, attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            cache.set(ip_key, ip_attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            raise InvalidOrExpiredCode()

        with transaction.atomic():
            if user.account_status == User.AccountStatus.DEACTIVATED:
                user.activate()
                log_audit_event(
                    actor=user, entity_type="user", entity_id=user.pk, action="reactivate",
                    after_state={"by": "returning_supervisor"},
                )
            # Their supervisor role, to register students with, unless they still hold it.
            if not user_has_role(user, ROLE_SUPERVISOR):
                RoleAssignmentHistory.objects.create(
                    user=user, role=get_role_by_name(ROLE_SUPERVISOR), valid_from=timezone.now(), valid_to=None,
                )

        login(request, user)
        cache.delete(cache_key)
        cache.delete(ip_key)
        logger.info("returning_supervisor: signed in email_tag=%s ip=%s", email_log_tag(email), ip)
        return Response({
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            # login() rotates the CSRF token; the page carries on with the new one.
            "csrfToken": get_token(request),
        })
