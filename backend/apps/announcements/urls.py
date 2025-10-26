from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet

app_name = "announcements"

router = DefaultRouter()
router.register("", AnnouncementViewSet, basename="announcement")

urlpatterns = router.urls
