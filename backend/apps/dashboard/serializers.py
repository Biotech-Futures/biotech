from rest_framework import serializers


class DashboardNextEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_name = serializers.CharField()
    start_datetime = serializers.DateTimeField()
    location = serializers.CharField(allow_null=True, allow_blank=True)
    link = serializers.URLField(allow_null=True, allow_blank=True)
    is_virtual = serializers.BooleanField()


class DashboardSummarySerializer(serializers.Serializer):
    user = serializers.CharField()
    stats = serializers.DictField()

class GroupPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    track_id = serializers.IntegerField()
    track_name = serializers.CharField()
    member_count = serializers.IntegerField()
    lead_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()