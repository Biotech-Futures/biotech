from rest_framework.permissions import BasePermission

from apps.users.models import AdminScope

from .models import CertificatesRelease, MarksRelease


class IsGrader(BasePermission):
    """Any admin may grade: staff, superuser, or platform admin (AdminScope row)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return AdminScope.objects.filter(user=user).exists()


class MarksReleased(BasePermission):
    """Gate student- and supervisor-facing read views on the global release toggle."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        release = MarksRelease.load()
        return release.released_at is not None


class CertificatesReleased(BasePermission):
    """Gate certificate downloads on their own toggle, independent of marks."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        release = CertificatesRelease.load()
        return release.released_at is not None


class AnythingReleased(BasePermission):
    """Open once marks OR certificates are out.

    For the supervisor bundle, which adapts its contents to whichever gates
    are open — requiring both would withhold documents that are already
    public, requiring only marks would leak unreleased certificates.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            MarksRelease.load().released_at is not None
            or CertificatesRelease.load().released_at is not None
        )
