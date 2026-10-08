from rest_framework import serializers
from django.db import transaction

from apps.common.matching_weights import WEIGHT_FIELDS

from .models import MatchRecommendation, MatchRun, MatchingConfig


class MatchRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchRecommendation
        fields = ["id", "match_run", "group", "mentor_user", "score", "explanation", "accepted"]


class MatchRunSerializer(serializers.ModelSerializer):
    recommendations = MatchRecommendationSerializer(many=True, read_only=True)

    class Meta:
        model = MatchRun
        fields = ["id", "initiated_by_user", "run_type", "rules_snapshot", "created_at", "recommendations"]
        read_only_fields = ["id", "created_at", "recommendations"]


class BulkRecommendationAcceptSerializer(serializers.Serializer):
    recommendation_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class MatchingConfigSerializer(serializers.ModelSerializer):
    total_weight = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = MatchingConfig
        fields = [
            "id",
            "name",
            "is_active",
            "year_weight",
            "timezone_weight",
            "timezone_max_weight",
            "size_bonus_weight",
            "total_weight",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_weight", "created_at", "updated_at"]

    def validate(self, attrs):
        # Check the sum against the merged instance, so a PATCH that only sends
        # one weight is still validated against the whole set.
        instance = MatchingConfig(**{**self._stored_weights(), **attrs})
        error = instance.weight_total_error()
        if error:
            raise serializers.ValidationError({"weight_total": error})
        return attrs

    def _stored_weights(self) -> dict:
        if not self.instance:
            return {}
        return {
            field_name: getattr(self.instance, field_name)
            for field_name, _ in WEIGHT_FIELDS
        }

    def _record_editor(self, validated_data: dict) -> dict:
        request = self.context.get("request")
        if request is not None and request.user is not None and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return validated_data

    def create(self, validated_data):
        self._record_editor(validated_data)
        with transaction.atomic():
            config = MatchingConfig(**validated_data)
            # Only one config can be in force, so retire the previous one in the
            # same transaction a matching run could read from.
            if config.is_active:
                config.activate(commit=False)
            config.save()
        return config

    def update(self, instance, validated_data):
        self._record_editor(validated_data)
        with transaction.atomic():
            if validated_data.get("is_active", instance.is_active):
                instance.activate(commit=False)
            return super().update(instance, validated_data)