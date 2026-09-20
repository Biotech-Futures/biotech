from django.db import transaction
from django.db.models import Prefetch
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.common.rbac import active_role_ids, is_admin

from .models import RoleTask, RoleTaskCompletion, TaskStatus
from .serializers import RoleTaskMineSerializer, TaskToggleSerializer


def _with_my_completion(queryset, user):
    """Attach each row's completion for `user` (if any) as `.my_completions`,
    via a single extra query rather than one per role task."""
    return queryset.prefetch_related(
        Prefetch(
            "completions",
            queryset=RoleTaskCompletion.objects.filter(user=user),
            to_attr="my_completions",
        )
    )


def _visible_role_tasks(user):
    """Role tasks a user can act on: everyone currently holding the role
    (live join against RoleAssignmentHistory via active_role_ids — no
    fan-out, no backfill needed), plus admins for oversight/QA."""
    qs = RoleTask.objects.active().select_related("role")
    if is_admin(user):
        return qs
    return qs.filter(role_id__in=active_role_ids(user))


class RoleTaskMineListView(generics.ListAPIView):
    """GET /api/v1/tasks/role-tasks/mine/ — role tasks for the current user's
    active roles, each merged with the user's own completion state."""

    serializer_class = RoleTaskMineSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = RoleTask.objects.active().select_related("role").filter(
            role_id__in=active_role_ids(user)
        )
        return _with_my_completion(qs, user).order_by("due_date", "id")


class RoleTaskToggleView(generics.GenericAPIView):
    """POST /api/v1/tasks/role-tasks/<id>/check/ — flip/set the current
    user's own completion on a role task. Creates the RoleTaskCompletion row
    on first call (lazily) rather than it having been fanned out in advance."""

    serializer_class = TaskToggleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _visible_role_tasks(self.request.user)

    def post(self, request, *args, **kwargs):
        role_task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_value = serializer.validated_data.get("completed")

        with transaction.atomic():
            completion, _created = RoleTaskCompletion.objects.get_or_create(
                role_task=role_task,
                user=request.user,
                defaults={"status": TaskStatus.TODO},
            )
            completion.completed = (not completion.completed) if new_value is None else new_value
            completion.save(update_fields=["completed", "updated_at"])

        role_task = _with_my_completion(
            RoleTask.objects.filter(pk=role_task.pk).select_related("role"),
            request.user,
        ).get()
        return Response(
            RoleTaskMineSerializer(role_task, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
