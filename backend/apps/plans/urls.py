"""Member plan endpoints, mounted at /api/v1/plans/ (GP3)."""

from django.urls import path

from . import views

app_name = "plans"
urlpatterns = [
    path(
        "groups/<int:group_id>/tasks/",
        views.GroupPlanTaskListView.as_view(),
        name="group-plan-tasks",
    ),
    path(
        "groups/<int:group_id>/tasks/<int:task_id>/check/",
        views.GroupPlanTaskCheckView.as_view(),
        name="group-plan-task-check",
    ),
]
