from django.urls import path
from . import views
from .views import TaskRetrieveview, TaskRetrieveUpdateView, MilestoneListHTMLView, TaskCreateView, TaskListHTMLView, DeleteTaskView

urlpatterns = [
    path("api/v1/tasks/<int:pk>/", TaskRetrieveUpdateView.as_view(), name="task-detail"),
    path("api/v1/milestones/", MilestoneListHTMLView.as_view(), name="milestone-list"),
    path("api/v1/createtask", TaskCreateView.as_view(), name="task-create"),
    path("api/v1/tasks/", TaskListHTMLView.as_view(), name="task-list"),
    path("api/v1/tasks/delete/<int:pk>/", DeleteTaskView.as_view(), name="task-delete")
]