from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .filters import TaskFilter
from .models import Task
from .permissions import (
    CanToggleTask,
    IsTaskManager,
    resolve_creator_role,
    visible_tasks,
)
from .serializers import (
    TaskCreateSerializer,
    TaskSerializer,
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
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter

    def get_queryset(self):
        return visible_tasks(self.request.user).order_by("id")

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
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTaskManager]

    def get_queryset(self):
        # Detail lookups use the visibility filter so non-visible tasks 404.
        return visible_tasks(self.request.user)

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return TaskUpdateSerializer
        return TaskSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_update(serializer)
        return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.deleted_at is not None:
            return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)
        instance.soft_delete()
        instance.refresh_from_db()
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

        with transaction.atomic():
            task.completed = (not task.completed) if new_value is None else new_value
            task.save(update_fields=["completed", "updated_at"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)
