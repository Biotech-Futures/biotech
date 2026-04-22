from django.urls import path
from .views import GroupsPreviewView, NextEventView, ProgressSnapshotView

urlpatterns = [
    path('v1/progress/', ProgressSnapshotView.as_view(), name='dashboard-progress'),
    path('v1/next-event/', NextEventView.as_view(), name='dashboard-next-event'),
    path('v1/groups-preview/', GroupsPreviewView.as_view(), name='dashboard-groups-preview'),
]
