from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import EventViewSet

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    # router provides:
    #   GET  /events/v1/   -> list
    #   POST /events/v1/   -> create
    path("", include(router.urls)),
]
