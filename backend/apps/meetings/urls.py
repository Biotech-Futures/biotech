from rest_framework.routers import DefaultRouter

from .views import GroupMeetingViewSet

router = DefaultRouter()
router.register(r'meetings', GroupMeetingViewSet, basename='meetings')
urlpatterns = router.urls
