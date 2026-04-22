from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.events.models import Events


# --- Progress Snapshot (#1) ---

class NextMilestoneSerializer(serializers.Serializer):
    """Nested representation of the next upcoming milestone inside a progress snapshot."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    due_date = serializers.DateTimeField(allow_null=True)


class ProgressScopeSerializer(serializers.Serializer):
    """Describes whose data the progress snapshot covers so the frontend can display context."""
    type = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    group_id = serializers.IntegerField(allow_null=True)
    track_id = serializers.IntegerField(allow_null=True)


class ProgressSnapshotSerializer(serializers.Serializer):
    """Full response shape for GET /dashboard/v1/progress/."""
    completion_rate = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    current_stage = serializers.CharField(allow_null=True)
    next_milestone = NextMilestoneSerializer(allow_null=True)
    scope = ProgressScopeSerializer()
    updated_at = serializers.DateTimeField()


# --- Next Event (#2) ---

class NextEventSerializer(serializers.ModelSerializer):
    """
    Response shape for GET /dashboard/v1/next-event/.

    Extends the base Events model with two fields that are not stored directly on
    the event row and must be resolved at request time:
      - group: first EventTargetGroup for this event (passed via serializer context).
      - rsvp_status: the requesting user's RSVP record (passed via serializer context).

    Both fields are injected through context by NextEventView._build_response() to avoid
    additional per-serializer queries inside the serializer itself.
    """
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
