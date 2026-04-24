from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DashboardNextEventView, DashboardViewSet, GroupsPreviewView

router = DefaultRouter()
router.register("", DashboardViewSet, basename="dashboard")

urlpatterns = [
    *router.urls,
    path("next-event/", DashboardNextEventView.as_view(), name="dashboard-next-event"),
    path("groups-preview/", GroupsPreviewView.as_view(), name="dashboard-groups-preview"),
]
