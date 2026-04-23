from django.urls import path

from .views import DashboardNextEventView


urlpatterns = [
    path("v1/next-event/", DashboardNextEventView.as_view(), name="dashboard-next-event"),
]
