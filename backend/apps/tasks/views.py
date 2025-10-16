from django.shortcuts import render, get_object_or_404
from rest_framework.response import Response
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from .models import Tasks, Milestone
from .serializers import TaskSerializer, MilestoneSerializer, TaskCreateSerializer
from rest_framework.views import APIView
from django.db import transaction

# Create your views here.
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
        data=request.data
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

class TaskCreateView(generics.CreateAPIView):
    queryset = Tasks.objects.select_related("milestone")
    serializer_class = TaskCreateSerializer
    permission_classes = [permissions.AllowAny]

class TaskListHTMLView(generics.ListAPIView):
    # queryset = Tasks.objects.select_related("milestone")
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]

    pagination_class = TaskPagePagination

    def get_queryset(self):
        queryset = Tasks.objects.all()
        milestone_param = self.request.query_params.get("milestone")
        if milestone_param is not None:
            queryset = queryset.filter(milestone=milestone_param)
        delete_param = self.request.query_params.get("deleted")
        if delete_param is not None:
            queryset = queryset.filter(deleted_flag=delete_param)
        return queryset
    
class DeleteTaskView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        task_id = kwargs.get("pk")

        task = get_object_or_404(Tasks, pk=task_id)
        task.deleted_flag = True
        task.save()

        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)