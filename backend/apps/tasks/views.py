from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.audit.services import log_audit_event

from .filters import TaskFilter
from .models import Task, TaskStatus
from .permissions import (
    CanToggleTask,
    IsTaskManager,
    resolve_creator_role,
    visible_tasks,
)
from .serializers import (
    TaskCreateSerializer,
    TaskSerializer,
    TaskStatusUpdateSerializer,
    TaskToggleSerializer,
    TaskUpdateSerializer,
)


class TaskPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class TaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTaskManager]
    pagination_class = TaskPagePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["name", "description"]
    ordering_fields = ["due_date", "created_at", "updated_at", "status"]
    ordering = ["id"]

    def get_queryset(self):
        return (
            visible_tasks(self.request.user)
            .select_related("created_by", "assigned_user")
            .order_by("id")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TaskCreateSerializer
        return TaskSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            task_type = serializer.validated_data["task_type"]
            group = serializer.validated_data.get("group")
            assigned_user = serializer.validated_data.get("assigned_user")
            creator_role = resolve_creator_role(
                request.user, task_type, group=group, assigned_user=assigned_user
            )
            task = serializer.save(created_by=request.user, creator_role=creator_role)
        log_audit_event(
            actor=request.user,
            entity_type="task",
            entity_id=task.id,
            action="create",
            after_state=TaskSerializer(task).data,
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTaskManager]

    def get_queryset(self):
        # Detail lookups use the visibility filter so non-visible tasks 404.
        return visible_tasks(self.request.user).select_related(
            "created_by", "assigned_user"
        )

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return TaskUpdateSerializer
        return TaskSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        before_state = TaskSerializer(instance).data
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_update(serializer)
        instance.refresh_from_db()
        log_audit_event(
            actor=request.user,
            entity_type="task",
            entity_id=instance.id,
            action="update",
            before_state=before_state,
            after_state=TaskSerializer(instance).data,
        )
        return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.deleted_at is not None:
            return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)
        before_state = TaskSerializer(instance).data
        instance.soft_delete()
        instance.refresh_from_db()
        log_audit_event(
            actor=request.user,
            entity_type="task",
            entity_id=instance.id,
            action="delete",
            before_state=before_state,
            after_state=TaskSerializer(instance).data,
        )
        return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)


class TaskToggleView(generics.GenericAPIView):
    queryset = Task.objects.filter(deleted_at__isnull=True)
    serializer_class = TaskToggleSerializer
    permission_classes = [permissions.IsAuthenticated, CanToggleTask]

    def post(self, request, *args, **kwargs):
        task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_value = serializer.validated_data.get("completed")

        before_completed = task.completed
        with transaction.atomic():
            task.completed = (not task.completed) if new_value is None else new_value
            task.save(update_fields=["completed", "updated_at"])
        log_audit_event(
            actor=request.user,
            entity_type="task",
            entity_id=task.id,
            action="toggle",
            before_state={"completed": before_completed},
            after_state={"completed": task.completed},
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)


class TaskBulkToggleView(generics.GenericAPIView):
    """POST /api/v1/tasks/bulk/check/ — flip/set `completed` on up to 200 tasks.

    Per-row permission via CanToggleTask; ungranted rows fall into `forbidden`
    rather than failing the whole call.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        ids = request.data.get("task_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            return Response(
                {"task_ids": ["Must be a non-empty list of integers."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(ids) > 200:
            return Response(
                {"task_ids": ["At most 200 tasks per call."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        completed_value = request.data.get("completed")
        if completed_value is not None and not isinstance(completed_value, bool):
            return Response(
                {"completed": ["Must be a boolean if provided."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gate = CanToggleTask()
        updated = []
        not_found = []
        forbidden = []

        with transaction.atomic():
            tasks_qs = Task.objects.filter(id__in=ids, deleted_at__isnull=True)
            tasks_by_id = {t.id: t for t in tasks_qs.select_for_update()}
            for task_id in ids:
                task = tasks_by_id.get(task_id)
                if task is None:
                    not_found.append(task_id)
                    continue
                if not gate.has_object_permission(request, self, task):
                    forbidden.append(task_id)
                    continue
                before_completed = task.completed
                task.completed = (not task.completed) if completed_value is None else completed_value
                task.save(update_fields=["completed", "updated_at"])
                log_audit_event(
                    actor=request.user,
                    entity_type="task",
                    entity_id=task.id,
                    action="toggle",
                    before_state={"completed": before_completed},
                    after_state={"completed": task.completed},
                )
                updated.append(task)

        return Response(
            {
                "updated": TaskSerializer(updated, many=True).data,
                "not_found": not_found,
                "forbidden": forbidden,
            },
            status=status.HTTP_200_OK,
        )


class TaskStatusUpdateView(generics.GenericAPIView):
    """POST /api/v1/tasks/<id>/status/ — change task status without entering
    full edit. Permission gate mirrors CanToggleTask: assignee, mentor of
    group, supervisor of assignee, track admin, or task creator can change.
    Setting status to "done" also flips `completed=True`; any other status
    flips `completed=False`."""

    queryset = Task.objects.filter(deleted_at__isnull=True)
    serializer_class = TaskStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, CanToggleTask]

    def post(self, request, *args, **kwargs):
        task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        before_state = {"status": task.status, "completed": task.completed}
        new_completed = new_status == TaskStatus.DONE
        with transaction.atomic():
            task.status = new_status
            task.completed = new_completed
            task.save(update_fields=["status", "completed", "updated_at"])
        log_audit_event(
            actor=request.user,
            entity_type="task",
            entity_id=task.id,
            action="status_change",
            before_state=before_state,
            after_state={"status": task.status, "completed": task.completed},
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)
