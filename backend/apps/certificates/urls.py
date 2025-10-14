from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import MentorCertificateViewSet

router = SimpleRouter()
# yields: /certificates/v1/{pk}/
router.register(r"v1", MentorCertificateViewSet, basename="certificates")

urlpatterns = [
    path("", include(router.urls)),
]
