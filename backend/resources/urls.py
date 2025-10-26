from rest_framework.routers import DefaultRouter

from .views import ResourceViewSet

app_name = "resources"

router = DefaultRouter()
router.register("", ResourceViewSet, basename="resource")

urlpatterns = router.urls
