from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import MentorCertificateViewSet

router = SimpleRouter()
# Canonical route at the app root. Yields ``/certificates/{pk}/``,
# ``/certificates/{pk}/verify/`` etc. — exposed as legacy ``/certificates/...``
# and canonical ``/api/v1/certificates/...`` by config.urls.
router.register(r"", MentorCertificateViewSet, basename="certificates")

_canonical = [
    path("", include(router.urls)),
]

urlpatterns = [
    # Legacy ``/certificates/v1/...`` alias — see apps.announcements.urls for
    # the ordering rationale. Drop once consumers move off the ``v1/`` segment.
    path("v1/", include(_canonical)),
    *_canonical,
]
