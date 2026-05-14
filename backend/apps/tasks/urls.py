from django.urls import path

from .views import (
    TaskBulkToggleView,
    TaskListCreateView,
    TaskRetrieveUpdateDestroyView,
    TaskRestoreView,
    TaskToggleView,
)

urlpatterns = [
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("bulk/check/", TaskBulkToggleView.as_view(), name="task-bulk-toggle"),
    # Restore is a dedicated mutation; clients should not PATCH deleted_at.
    path("<int:pk>/restore/", TaskRestoreView.as_view(), name="task-restore"),
    path("<int:pk>/", TaskRetrieveUpdateDestroyView.as_view(), name="task-detail"),
    path("<int:pk>/check/", TaskToggleView.as_view(), name="task-toggle"),
]
