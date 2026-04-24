from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import MatchRecommendationViewSet, MatchRunViewSet

router = SimpleRouter()
router.register(r"v1/runs", MatchRunViewSet, basename="match-runs")
router.register(r"v1/recommendations", MatchRecommendationViewSet, basename="match-recommendations")

urlpatterns = [
    path("", include(router.urls)),
]

