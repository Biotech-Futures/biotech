from rest_framework import serializers

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
        # ``save()`` replaces any previous row: there is only ever one config.
        return MatchingConfig.objects.create(**validated_data)

    def update(self, instance, validated_data):
        self._record_editor(validated_data)
        return super().update(instance, validated_data)