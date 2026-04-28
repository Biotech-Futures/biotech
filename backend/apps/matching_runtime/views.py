from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema

from apps.audit.services import log_audit_event
from apps.groups.services import assign_mentor_to_group
from apps.users.utils.admin_scope import can_admin_track, is_operational_admin

from .models import MatchRecommendation, MatchRun
from .serializers import BulkRecommendationAcceptSerializer, MatchRecommendationSerializer, MatchRunSerializer


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

    @extend_schema(request=BulkRecommendationAcceptSerializer, responses={200: MatchRecommendationSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="bulk-accept")
    @transaction.atomic
    def bulk_accept(self, request):
        if not is_operational_admin(request.user):
            raise PermissionDenied("Operational admin access is required.")

        serializer = BulkRecommendationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recommendation_ids = serializer.validated_data["recommendation_ids"]
        recommendations = list(
            MatchRecommendation.objects.select_related("group__track", "mentor_user")
            .filter(id__in=recommendation_ids)
            .order_by("id")
        )
        found_ids = {recommendation.id for recommendation in recommendations}
        missing_ids = [recommendation_id for recommendation_id in recommendation_ids if recommendation_id not in found_ids]
        if missing_ids:
            raise ValidationError({"missing_recommendation_ids": missing_ids})

        for recommendation in recommendations:
            if not can_admin_track(request.user, recommendation.group.track_id):
                raise PermissionDenied("You do not have admin scope for one or more recommendation tracks.")
            try:
                assign_mentor_to_group(
                    group=recommendation.group,
                    mentor_user=recommendation.mentor_user,
                    replace_existing=True,
                )
            except DjangoValidationError as exc:
                raise ValidationError({str(recommendation.id): exc.messages}) from exc
            recommendation.accepted = True
            recommendation.save(update_fields=["accepted"])
            log_audit_event(
                actor=request.user,
                entity_type="match_recommendation",
                entity_id=recommendation.id,
                action="accept",
                after_state=MatchRecommendationSerializer(recommendation).data,
            )

        return Response(MatchRecommendationSerializer(recommendations, many=True).data, status=status.HTTP_200_OK)
