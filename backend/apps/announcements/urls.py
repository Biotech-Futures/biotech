from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AnnouncementViewSet

router = SimpleRouter()
router.register(r"v1", AnnouncementViewSet, basename="announcements")

urlpatterns = [
    path("", include(router.urls)),
]
