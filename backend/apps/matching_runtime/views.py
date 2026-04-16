from rest_framework import mixins, permissions, viewsets

from apps.audit.services import log_audit_event

from .models import MatchRecommendation, MatchRun
from .serializers import MatchRecommendationSerializer, MatchRunSerializer


class MatchRunViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = MatchRun.objects.select_related("initiated_by_user", "track").prefetch_related("recommendations").all()
    serializer_class = MatchRunSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        match_run = serializer.save(initiated_by_user=self.request.user)
        log_audit_event(
            actor=self.request.user,
            entity_type="match_run",
            entity_id=match_run.id,
            action="create",
            after_state=MatchRunSerializer(match_run).data,
        )


class MatchRecommendationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = MatchRecommendation.objects.select_related("match_run", "group", "mentor_user").all()
    serializer_class = MatchRecommendationSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        recommendation = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="match_recommendation",
            entity_id=recommendation.id,
            action="create",
            after_state=MatchRecommendationSerializer(recommendation).data,
        )

