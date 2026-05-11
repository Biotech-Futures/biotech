from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import MatchRecommendationViewSet, MatchRunViewSet

router = SimpleRouter()
# Canonical routes at the app root. Exposed as legacy ``/matching/runs/`` and
# ``/matching/recommendations/`` and canonical ``/api/v1/matching/...`` by
# config.urls.
router.register(r"runs", MatchRunViewSet, basename="match-runs")
router.register(r"recommendations", MatchRecommendationViewSet, basename="match-recommendations")

_canonical = [
    path("", include(router.urls)),
]

urlpatterns = [
    # Legacy ``/matching/v1/runs/`` / ``/matching/v1/recommendations/`` alias —
    # see apps.announcements.urls for the ordering rationale. Drop once all
    # consumers move off the ``v1/`` segment.
    path("v1/", include(_canonical)),
    *_canonical,
]
