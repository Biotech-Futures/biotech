"""Management's Registration switch: whether registration is open to the
public. Open until an admin closes it; while closed, the sign-in page has no
Register now and students can't register themselves (a late link still can)."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin

from ..models import PublicRegistrationSetting


class RegistrationOpenView(APIView):
    """GET ``{"open": bool}`` for anyone, signed in or not, so the sign-in and
    registration pages can follow it; PUT ``{"open": bool}`` for admins only."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"open": PublicRegistrationSetting.load().open})

    def put(self, request):
        if not is_admin(request.user):
            return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)
        value = request.data.get("open")
        if not isinstance(value, bool):
            return Response({"detail": "open must be true or false."}, status=status.HTTP_400_BAD_REQUEST)
        setting = PublicRegistrationSetting.load()
        setting.open = value
        setting.updated_by = request.user
        setting.save()
        return Response({"open": setting.open})
