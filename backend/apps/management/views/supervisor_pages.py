"""Management's Pages Visibility (on Challenge Start): when students, mentors
and supervisors start seeing Home, Groups, Events, Announcements and
Resources. Hidden until its date and time, and while none is set, so a
student or mentor sees only their profile, and a supervisor only their own
pages (My Profile, Registration, Students, Groups). Admins always see them."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin

from ..models import SupervisorPagesSetting
from ..services.send_guard import person_name


def state(setting):
    """Whether the pages are shown now, from when, and who last set it."""
    return {
        "shown": setting.shown_at(timezone.now()),
        "shown_from": setting.shown_from.isoformat() if setting.shown_from else None,
        "set_by": person_name(setting.updated_by) if setting.updated_by else "",
        "updated_at": setting.updated_at.isoformat() if setting.updated_by and setting.updated_at else None,
    }


class SupervisorPagesView(APIView):
    """GET ``{"shown", "shown_from", "set_by", "updated_at"}`` for anyone
    signed in, so their menu can follow it; PUT ``{"shown_from"}`` (a date and
    time, or null for none), for admins only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(state(SupervisorPagesSetting.load()))

    def put(self, request):
        if not is_admin(request.user):
            return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)
        if "shown_from" not in request.data:
            return Response(
                {"detail": "Give shown_from, as a date and time or null."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            shown_from = serializers.DateTimeField(allow_null=True).run_validation(request.data["shown_from"])
        except serializers.ValidationError:
            return Response(
                {"detail": "Give shown_from, as a date and time or null."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        setting = SupervisorPagesSetting.load()
        setting.shown_from = shown_from
        setting.updated_by = request.user
        setting.save()
        return Response(state(setting))
