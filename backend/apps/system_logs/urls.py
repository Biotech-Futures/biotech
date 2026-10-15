"""Mounted at ``/api/v1/admin/system-logs/`` by ``apps.admin.urls``."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.SystemLogListView.as_view(), name="system-log-list"),
    # Literal segments precede <int:pk>.
    path("export/", views.SystemLogExportView.as_view(), name="system-log-export"),
    path("prune/", views.PruneSystemLogsView.as_view(), name="system-log-prune"),
    path("<int:pk>/", views.SystemLogDetailView.as_view(), name="system-log-detail"),
]
