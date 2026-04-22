from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.events.models import Events


class NextMilestoneSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    due_date = serializers.DateTimeField(allow_null=True)


class ProgressScopeSerializer(serializers.Serializer):
    type = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    group_id = serializers.IntegerField(allow_null=True)
    track_id = serializers.IntegerField(allow_null=True)


class ProgressSnapshotSerializer(serializers.Serializer):
    completion_rate = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    current_stage = serializers.CharField(allow_null=True)
    next_milestone = NextMilestoneSerializer(allow_null=True)
    scope = ProgressScopeSerializer()
    updated_at = serializers.DateTimeField()


class NextEventSerializer(serializers.ModelSerializer):
    group = serializers.SerializerMethodField()
    rsvp_status = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_group(self, obj):
        return self.context.get('group_id')

    @extend_schema_field(serializers.ChoiceField(choices=['pending', 'going', 'maybe', 'declined']))
    def get_rsvp_status(self, obj):
        return self.context.get('rsvp_status', 'pending')

    class Meta:
        model = Events
        fields = [
            'id', 'event_name', 'description', 'track', 'group',
            'event_type', 'start_datetime', 'ends_datetime',
            'location', 'humanitix_link', 'event_image', 'is_virtual',
            'rsvp_status',
        ]
