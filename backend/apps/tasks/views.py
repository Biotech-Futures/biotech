from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from .filters import MilestoneFilter, TaskFilter
from .models import Tasks, Milestone
from .serializers import TaskSerializer, MilestoneSerializer, TaskCreateSerializer, DeleteTaskResponseSerializer, MilestoneProgressSerializer, ProgressSnapshotSerializer, ProgressQuerySerializer
from .services import build_progress_snapshot, get_allowed_group_ids


class TaskRetrieveview(generics.RetrieveAPIView):
    queryset = Tasks.objects.select_related("milestone")
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]


class TaskRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Tasks.objects.select_related("milestone")
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        return TaskSerializer

    def patch(self, request, *args, **kwargs):
        task = self.get_object()
        data = request.data
        if "task_name" in data:
            task.task_name = data["task_name"]
            task.save(update_fields=["task_name"])

        if "task_description" in data:
            task.task_description = data["task_description"]
            task.save(update_fields=["task_description"])

        if "milestone_id" in data:
            milestone = get_object_or_404(Milestone, pk=data["milestone_id"])
            task.milestone = milestone
            task.save(update_fields=["milestone"])

        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)


class TaskPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class MilestoneListHTMLView(generics.ListAPIView):
    queryset = Milestone.objects.all()
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TaskPagePagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = MilestoneFilter


class TaskCreateView(generics.CreateAPIView):
    queryset = Tasks.objects.select_related("milestone")
    serializer_class = TaskCreateSerializer
    permission_classes = [permissions.AllowAny]


class TaskListHTMLView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TaskPagePagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter
    queryset = Tasks.objects.all()


class DashboardProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query_serializer = ProgressQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        group_id = query_serializer.validated_data.get("group_id")

        if group_id is not None:
            allowed_ids = get_allowed_group_ids(request.user)
            if group_id not in allowed_ids:
                return Response(
                    {"detail": "You do not have access to this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        snapshot = build_progress_snapshot(group_id=group_id)
        return Response(ProgressSnapshotSerializer(snapshot).data, status=status.HTTP_200_OK)


class DeleteTaskView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=None,
        responses={200: DeleteTaskResponseSerializer},
    )
    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        task_id = kwargs.get("pk")
        task = get_object_or_404(Tasks, pk=task_id)
        task.deleted_at = timezone.now()
        task.save(update_fields=["deleted_at"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)
