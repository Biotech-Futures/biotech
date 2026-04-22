from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.events.models import Events
from apps.groups.models import GroupMembership, Groups
from apps.groups.services import MENTOR_MEMBERSHIP_ROLE


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


# --- Groups Preview (dashboard dedicated endpoint) ---

class DashboardLeadUserSerializer(serializers.Serializer):
    """Minimal lead-user shape returned inside a group preview row."""
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class DashboardGroupPreviewSerializer(serializers.ModelSerializer):
    """
    Flattened, UI-specific group projection for GET /dashboard/v1/groups-preview/.

    Design decisions:
    - member_count is a plain IntegerField, not a SerializerMethodField.
      It reads directly from the ORM annotation added by the view's get_queryset(),
      so no Python loops or extra queries are needed for this field.
    - track_id / track_name are read from the FK integer column and the
      select_related('track') join respectively — both zero extra queries.
    - lead_user / lead_name are resolved from the `mentor_memberships` list
      attached by prefetch_related() in the view, so the cost is one additional
      batched query for all groups in the page, not one per group.
    """
    # Reads the FK integer column directly (no JOIN needed).
    # DRF resolves field name `track_id` to obj.track_id automatically.
    track_id = serializers.IntegerField()
    # Satisfied by select_related('track') in the view queryset.
    track_name = serializers.CharField(source='track.track_name', read_only=True)
    # Populated from the ORM annotation; DRF reads it as a plain attribute.
    member_count = serializers.IntegerField()
    lead_user = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def _lead_membership(self, obj):
        # Prefers the prefetched `mentor_memberships` list (one batched query for the
        # whole page). Falls back to a single query when called outside a list context.
        memberships = getattr(obj, 'mentor_memberships', None)
        if memberships is not None:
            return memberships[0] if memberships else None
        return (
            GroupMembership.objects
            .filter(group=obj, membership_role__iexact=MENTOR_MEMBERSHIP_ROLE, left_at__isnull=True)
            .select_related('user')
            .first()
        )

    @extend_schema_field(DashboardLeadUserSerializer(allow_null=True))
    def get_lead_user(self, obj):
        m = self._lead_membership(obj)
        if not m:
            return None
        return {'id': m.user.id, 'first_name': m.user.first_name, 'last_name': m.user.last_name}

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_lead_name(self, obj):
        m = self._lead_membership(obj)
        if not m:
            return None
        return f"{m.user.first_name} {m.user.last_name}".strip()

    @extend_schema_field(serializers.ChoiceField(choices=['active', 'deleted']))
    def get_status(self, obj):
        return 'deleted' if obj.deleted_at else 'active'

    class Meta:
        model = Groups
        fields = ['id', 'group_name', 'track_id', 'track_name', 'member_count',
                  'lead_user', 'lead_name', 'status']


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
