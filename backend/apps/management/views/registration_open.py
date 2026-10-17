"""Whether registration is open, by the year's dates (Management >
Registration Visibility > Registration Dates): for the sign-in page's Register
now and the registration page. While closed, students can't register
themselves (a late link still can), nor supervisors register students, but
for those let register after it closes (Supervisors After Close)."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin
from apps.users.models import SupervisorProfile
from apps.users.registration_intake import current_window, registers_after_close


def registration_state(user) -> dict:
    """Whether the public can register now (``open_now``), the dates, and, for
    a supervisor or an admin, whether they can register students now
    (``can_register_students``)."""
    window = current_window()
    within_dates = window.is_open(timezone.now())
    state = {
        "open_now": within_dates,
        "opens_at": window.opens_at,
        "closes_at": window.closes_at,
    }
    if getattr(user, "is_authenticated", False) and (
        is_admin(user) or SupervisorProfile.objects.filter(user=user).exists()
    ):
        state["can_register_students"] = within_dates or registers_after_close(user)
    return state


class RegistrationOpenView(APIView):
    """GET ``registration_state`` for anyone, signed in or not, so the sign-in
    and registration pages can follow it."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(registration_state(request.user))
