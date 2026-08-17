from rest_framework.permissions import BasePermission

from .models import MarksRelease


class IsGrader(BasePermission):
    """Admin-only write access. Broadened later if a dedicated grader role is added."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class MarksReleased(BasePermission):
    """Gate student- and supervisor-facing read views on the global release toggle."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        release = MarksRelease.load()
        return release.released_at is not None
