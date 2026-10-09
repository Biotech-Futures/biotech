from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.audit.services import log_audit_event
from apps.groups.services import assign_mentor_to_group
from apps.common.rbac import is_admin

from .models import MatchRecommendation, MatchRun, MatchingConfig
from .serializers import (
    BulkRecommendationAcceptSerializer,
    MatchRecommendationSerializer,
    MatchRunSerializer,
    MatchingConfigSerializer,
)
from .services import matching_config_defaults, resolve_scoring_weights


class MatchRunViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = MatchRun.objects.select_related("initiated_by_user").prefetch_related("recommendations").all()
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


class MatchingConfigViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Admin CRUD for the matching scoring weights.

    Weights are percentages that must total exactly 100; the serializer rejects
    anything else rather than normalising it. ``active`` and ``defaults`` are
    read-only shortcuts for the admin panel.
    """

    queryset = MatchingConfig.objects.select_related("updated_by").all()
    serializer_class = MatchingConfigSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        config = serializer.save()
        self._log_config_change(action="create", after_state=config)

    def perform_update(self, serializer):
        # Snapshot first: ``serializer.instance`` is the same object ``save()``
        # mutates, so reading it afterwards would record no change at all.
        before_state = MatchingConfigSerializer(serializer.instance).data
        config = serializer.save()
        self._log_config_change(
            action="update",
            before_state=before_state,
            after_state=config,
        )

    def perform_destroy(self, instance):
        # Capture the state before the row is gone, so the audit trail of a
        # deleted weight set stays readable.
        before_state = MatchingConfigSerializer(instance).data
        entity_id = instance.id
        instance.delete()
        log_audit_event(
            actor=self.request.user,
            entity_type="matching_config",
            entity_id=entity_id,
            action="delete",
            before_state=before_state,
        )

    def _log_config_change(self, *, action, after_state, before_state=None):
        log_audit_event(
            actor=self.request.user,
            entity_type="matching_config",
            entity_id=after_state.id,
            action=action,
            before_state=before_state,
            after_state=MatchingConfigSerializer(after_state).data,
        )

    @extend_schema(responses={200: MatchingConfigSerializer})
    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """The stored config (or its weights) the next run will use."""
        config = MatchingConfig.get_singleton()
        if config is None:
            return Response(
                {
                    "data": None,
                    "weights": resolve_scoring_weights().as_dict(),
                    **matching_config_defaults(),
                }
            )

        return Response(
            {
                "data": MatchingConfigSerializer(config).data,
                "weights": config.to_scoring_weights().as_dict(),
                **matching_config_defaults(),
            }
        )

    @extend_schema(
        responses={200: inline_serializer(
            name="MatchingConfigDefaults",
            fields={
                "requiredTotal": serializers.CharField(),
                "defaults": serializers.DictField(child=serializers.DecimalField(max_digits=5, decimal_places=2)),
            },
        )}
    )
    @action(detail=False, methods=["get"], url_path="defaults")
    def defaults(self, request):
        """A complete, valid weight split for an admin form to start from."""
        return Response({"data": matching_config_defaults()})


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
        if not is_admin(request.user):
            raise PermissionDenied("Admin access is required.")

        serializer = BulkRecommendationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recommendation_ids = serializer.validated_data["recommendation_ids"]
        recommendations = list(
            MatchRecommendation.objects.select_related("group", "mentor_user")
            .filter(id__in=recommendation_ids)
            .order_by("id")
        )
        found_ids = {recommendation.id for recommendation in recommendations}
        missing_ids = [recommendation_id for recommendation_id in recommendation_ids if recommendation_id not in found_ids]
        if missing_ids:
            raise ValidationError({"missing_recommendation_ids": missing_ids})

        for recommendation in recommendations:
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
