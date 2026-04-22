from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from .models import Tasks, Milestone, TaskAssignees
from .serializers import TaskSerializer, MilestoneSerializer, TaskCreateSerializer, DeleteTaskResponseSerializer
from rest_framework.views import APIView
from django.db import transaction
from drf_spectacular.utils import extend_schema


# Bug fix (#4): the previous implementation passed the raw query string value directly to
# the ORM (e.g. filter(deleted_flag="false")), which caused a 500 on PostgreSQL for any
# casing other than exactly "True"/"False".
# Now that Tasks and Milestone use deleted_at (a DateTimeField), the parsed boolean drives
# a __isnull lookup instead: True → deleted_at__isnull=False (deleted), False → isnull=True.
# This helper stays in place to normalise and validate all common string representations.
def _parse_bool_param(value: str) -> bool:
    """Parse common boolean query string representations.

    Accepts: true/True/1/yes → True  |  false/False/0/no → False
    Raises ValidationError (HTTP 400) for any other value.
    """
    normalised = value.strip().lower()
    if normalised in ('true', '1', 'yes'):
        return True
    if normalised in ('false', '0', 'no'):
        return False
    raise ValidationError('Invalid deleted value. Expected true or false.')


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

        # status is the single source of truth — no completed field to sync.
        if "status" in data:
            task.status = data["status"]
            task.save(update_fields=["status"])

        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)


class TaskPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class MilestoneListHTMLView(generics.ListAPIView):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TaskPagePagination

    def get_queryset(self):
        # Order by sort_order first so milestones respect their explicit sequence,
        # then fall back to id for stable ordering when sort_order values are equal.
        queryset = Milestone.objects.all().order_by('sort_order', 'id')

        # Added (#1): lets the dashboard and frontend filter milestones per group
        # without fetching all milestones and filtering client-side.
        group_id = self.request.query_params.get('group_id')
        if group_id is not None:
            queryset = queryset.filter(group_id=group_id)

        # ?deleted=false → deleted_at__isnull=True (active records only)
        # ?deleted=true  → deleted_at__isnull=False (soft-deleted records only)
        deleted_param = self.request.query_params.get('deleted')
        if deleted_param is not None:
            is_deleted = _parse_bool_param(deleted_param)
            queryset = queryset.filter(deleted_at__isnull=not is_deleted)

        return queryset


class TaskCreateView(generics.CreateAPIView):
    queryset = Tasks.objects.select_related("milestone")
    serializer_class = TaskCreateSerializer
    permission_classes = [permissions.AllowAny]


class TaskListHTMLView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TaskPagePagination

    def get_queryset(self):
        # select_related('milestone__group') satisfies TaskSerializer.get_group() with a
        # single JOIN instead of per-row queries.
        # prefetch_related('assignments__user') satisfies TaskSerializer.get_assignees()
        # in two batched queries regardless of how many tasks are returned.
        queryset = Tasks.objects.select_related(
            'milestone__group'
        ).prefetch_related(
            'assignments__user'
        )

        milestone_param = self.request.query_params.get("milestone")
        if milestone_param is not None:
            queryset = queryset.filter(milestone=milestone_param)

        # Added (#1): allows the dashboard to fetch tasks for a specific group directly,
        # traversing the task → milestone → group FK chain in the ORM.
        group_id = self.request.query_params.get("group_id")
        if group_id is not None:
            queryset = queryset.filter(milestone__group_id=group_id)

        # Bug fix (#4) + refactor: ?deleted=false → deleted_at__isnull=True (active only).
        # Accepts all common boolean string variants; returns HTTP 400 for invalid values.
        delete_param = self.request.query_params.get("deleted")
        if delete_param is not None:
            is_deleted = _parse_bool_param(delete_param)
            queryset = queryset.filter(deleted_at__isnull=not is_deleted)

        # Added (#1): ?assigned_to=me lets the dashboard fetch only the current user's tasks
        # without the frontend having to know task IDs or filter a large list client-side.
        assigned_to = self.request.query_params.get("assigned_to")
        if assigned_to == "me" and self.request.user.is_authenticated:
            task_ids = TaskAssignees.objects.filter(
                user=self.request.user,
                deleted_flag=False,
            ).values_list("task_id", flat=True)
            queryset = queryset.filter(id__in=task_ids)

        return queryset


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
        # Soft-delete by stamping the current time; deleted_at__isnull=True means active.
        task.deleted_at = timezone.now()
        task.save(update_fields=["deleted_at"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)
