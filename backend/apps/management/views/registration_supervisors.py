"""Management > Late Registration > Supervisors After Close: every
supervisor, and whether they can still register students while registration
is closed by its dates (``SupervisorProfile.register_after_close``)."""
from __future__ import annotations

from django.db.models import Count
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.users.models import StudentProfile, SupervisorProfile

from ..services.send_guard import person_name


def _row(profile, students: int) -> dict:
    user = profile.user
    return {
        "user_id": user.id,
        "name": person_name(user),
        "email": user.email,
        "school": profile.school_name or "",
        "students": students,
        "register_after_close": profile.register_after_close,
    }


def _student_count(user_id: int) -> int:
    return StudentProfile.objects.filter(supervisor_id=user_id).count()


class RegistrationSupervisorsView(APIView):
    """GET: a row per active supervisor, by name: ``user_id``, ``name``,
    ``email``, ``school``, ``students`` (how many they supervise) and
    ``register_after_close``."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        counts = dict(
            StudentProfile.objects.filter(supervisor__isnull=False)
            .values("supervisor_id")
            .annotate(students=Count("pk"))
            .values_list("supervisor_id", "students")
        )
        profiles = (
            SupervisorProfile.objects.filter(user__is_active=True)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "user_id")
        )
        # A supervisor profile's key is its user's id.
        return Response([_row(profile, counts.get(profile.pk, 0)) for profile in profiles])


class RegistrationSupervisorView(APIView):
    """PUT ``{"register_after_close": bool}``: whether this supervisor can
    still register students once registration closes. Answers with their row."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def put(self, request, user_id: int):
        value = request.data.get("register_after_close")
        if not isinstance(value, bool):
            return Response(
                {"detail": "register_after_close must be true or false."}, status=status.HTTP_400_BAD_REQUEST,
            )
        profile = SupervisorProfile.objects.select_related("user").filter(user_id=user_id).first()
        if profile is None:
            return Response({"detail": "No such supervisor."}, status=status.HTTP_404_NOT_FOUND)
        profile.register_after_close = value
        profile.save(update_fields=["register_after_close"])
        return Response(_row(profile, _student_count(user_id)))
