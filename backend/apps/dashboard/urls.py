from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DashboardNextEventView, DashboardViewSet

router = DefaultRouter()
router.register("", DashboardViewSet, basename="dashboard")

urlpatterns = [
    *router.urls,
    path("next-event/", DashboardNextEventView.as_view(), name="dashboard-next-event"),
]
