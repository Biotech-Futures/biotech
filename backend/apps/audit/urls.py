from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AuditLogViewSet

router = SimpleRouter()
# Canonical route at the app root — exposed as ``/audit/...`` (legacy mount)
# and ``/api/v1/audit/...`` (canonical) by config.urls.
router.register(r"", AuditLogViewSet, basename="audit-log")

_canonical = [
    path("", include(router.urls)),
]

urlpatterns = [
    # Legacy ``/audit/v1/...`` alias — see apps.announcements.urls for the
    # ordering rationale. Drop once consumers move off the ``v1/`` segment.
    path("v1/", include(_canonical)),
    *_canonical,
]
