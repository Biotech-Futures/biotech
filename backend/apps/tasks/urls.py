from django.urls import path

from .views import (
    TaskBulkToggleView,
    TaskListCreateView,
    TaskRetrieveUpdateDestroyView,
    TaskToggleView,
)

urlpatterns = [
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("bulk/check/", TaskBulkToggleView.as_view(), name="task-bulk-toggle"),
    path("<int:pk>/", TaskRetrieveUpdateDestroyView.as_view(), name="task-detail"),
    path("<int:pk>/check/", TaskToggleView.as_view(), name="task-toggle"),
]
