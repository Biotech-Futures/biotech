from rest_framework import serializers

from .models import MatchRecommendation, MatchRun


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
