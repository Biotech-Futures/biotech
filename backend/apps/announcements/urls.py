from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AnnouncementViewSet

router = SimpleRouter()
# Canonical route at the app root — exposed as ``/announcements/...`` (legacy
# mount) and ``/api/v1/announcements/...`` (canonical) by config.urls.
router.register(r"", AnnouncementViewSet, basename="announcements")

_canonical = [
    path("", include(router.urls)),
]

urlpatterns = [
    # Legacy ``/announcements/v1/...`` alias — preserves the original paths so
    # any client that hasn't migrated keeps resolving. Listed FIRST so the
    # canonical patterns below are the last named registration and win
    # ``reverse()`` lookups. Drop once all consumers move off the ``v1/``
    # segment.
    path("v1/", include(_canonical)),
    *_canonical,
]
