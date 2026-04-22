from django.urls import path
from .views import NextEventView, ProgressSnapshotView

urlpatterns = [
    path('v1/progress/', ProgressSnapshotView.as_view(), name='dashboard-progress'),
    path('v1/next-event/', NextEventView.as_view(), name='dashboard-next-event'),
]
