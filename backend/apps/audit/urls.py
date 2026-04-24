from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AuditLogViewSet

router = SimpleRouter()
router.register(r"v1", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("", include(router.urls)),
]

