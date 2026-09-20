from django.urls import path

from .role_task_views import RoleTaskMineListView, RoleTaskToggleView
from .views import (
    TaskBulkToggleView,
    TaskListCreateView,
    TaskRetrieveUpdateDestroyView,
    TaskRestoreView,
    TaskStatusUpdateView,
    TaskToggleView,
)

urlpatterns = [
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("bulk/check/", TaskBulkToggleView.as_view(), name="task-bulk-toggle"),
    # Restore is a dedicated mutation; clients should not PATCH deleted_at.
    path("<int:pk>/restore/", TaskRestoreView.as_view(), name="task-restore"),
    path("<int:pk>/", TaskRetrieveUpdateDestroyView.as_view(), name="task-detail"),
    path("<int:pk>/check/", TaskToggleView.as_view(), name="task-toggle"),
    path("<int:pk>/status/", TaskStatusUpdateView.as_view(), name="task-status"),
    # Role tasks: defined once per role (TK4), not per user — see
    # apps/tasks/role_task_views.py and apps/admin/services/role_task.py.
    # "mine/" must precede <int:pk> so the literal segment wins.
    path("role-tasks/mine/", RoleTaskMineListView.as_view(), name="role-task-mine-list"),
    path("role-tasks/<int:pk>/check/", RoleTaskToggleView.as_view(), name="role-task-toggle"),
]
