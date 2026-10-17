"""Management's Supervisor Visibility switches: whether supervisors see Home, Groups,
Events, Announcements and Resources (off until an admin turns it on, so a
supervisor sees only their own pages: My Profile, My Students, My Groups), and
whether they see their Registration page (on until an admin hides it)."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin

from ..models import SupervisorPagesSetting


# The switches, as GET and PUT name them.
SWITCHES = ("shown", "registration_shown")


def state(setting):
    return {name: getattr(setting, name) for name in SWITCHES}


class SupervisorPagesView(APIView):
    """GET ``{"shown": bool, "registration_shown": bool}`` for anyone signed
    in, so a supervisor's menu can follow them; PUT either or both, for admins
    only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(state(SupervisorPagesSetting.load()))

    def put(self, request):
        if not is_admin(request.user):
            return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)
        changes = {name: request.data[name] for name in SWITCHES if name in request.data}
        if not changes or not all(isinstance(value, bool) for value in changes.values()):
            return Response(
                {"detail": "Give shown or registration_shown, as true or false."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        setting = SupervisorPagesSetting.load()
        for name, value in changes.items():
            setattr(setting, name, value)
        setting.updated_by = request.user
        setting.save()
        return Response(state(setting))
