"""Management's Supervisor Visibility switch: whether supervisors see Home, Groups,
Events, Announcements and Resources. Off until an admin turns it on, so a
supervisor sees only their own pages (My Profile, My Students, My Groups)."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin

from ..models import SupervisorPagesSetting


class SupervisorPagesView(APIView):
    """GET ``{"shown": bool}`` for anyone signed in, so a supervisor's menu can
    follow it; PUT ``{"shown": bool}`` for admins only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"shown": SupervisorPagesSetting.load().shown})

    def put(self, request):
        if not is_admin(request.user):
            return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)
        shown = request.data.get("shown")
        if not isinstance(shown, bool):
            return Response({"detail": "shown must be true or false."}, status=status.HTTP_400_BAD_REQUEST)
        setting = SupervisorPagesSetting.load()
        setting.shown = shown
        setting.updated_by = request.user
        setting.save()
        return Response({"shown": setting.shown})
