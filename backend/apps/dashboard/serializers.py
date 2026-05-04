from rest_framework import serializers


class ProgressQuerySerializer(serializers.Serializer):
    group_id = serializers.IntegerField(required=False, allow_null=True)


class ProgressSnapshotSerializer(serializers.Serializer):
    completionRate = serializers.IntegerField()
    completedTasks = serializers.IntegerField()
    totalTasks = serializers.IntegerField()
    currentWeek = serializers.CharField(allow_null=True)
    nextMilestone = serializers.CharField(allow_null=True)
    nextMilestoneDate = serializers.DateTimeField(allow_null=True)


class DashboardNextEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_name = serializers.CharField()
    description = serializers.CharField(source='event_description', allow_null=True)
    track = serializers.IntegerField(source='track_id', allow_null=True)
    groups = serializers.ListField(child=serializers.IntegerField(), allow_empty=True, allow_null=True)
    event_type = serializers.CharField(allow_null=True)
    start_datetime = serializers.DateTimeField()
    ends_datetime = serializers.DateTimeField(allow_null=True)
    location = serializers.CharField(allow_null=True, allow_blank=True)
    location_link = serializers.URLField(allow_null=True, allow_blank=True)
    event_image = serializers.URLField(allow_null=True)
    is_virtual = serializers.BooleanField()
    rsvp_status = serializers.CharField(allow_null=True)


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