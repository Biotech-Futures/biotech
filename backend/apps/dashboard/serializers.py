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
    start_datetime = serializers.DateTimeField()
    location = serializers.CharField(allow_null=True, allow_blank=True)
    link = serializers.URLField(allow_null=True, allow_blank=True)
    is_virtual = serializers.BooleanField()


class DashboardSummarySerializer(serializers.Serializer):
    user = serializers.CharField()
    stats = serializers.DictField()


class DashboardGroupLeadUserSerializer(serializers.Serializer):
    """Nested lead object for groups-preview; mirrors the dashboard API contract."""

    id = serializers.IntegerField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)


class DashboardGroupPreviewSerializer(serializers.Serializer):
    """
    Flattened, UI-specific projection for the dashboard Groups Preview widget.

    Relies on annotated attributes produced by
    `apps.dashboard.services.get_groups_preview` so that member count and lead
    user information are resolved at the database level (no Python-side
    aggregation).
    """

    group_id = serializers.IntegerField(source="id")
    group_name = serializers.CharField()
    track_id = serializers.IntegerField()
    track_name = serializers.CharField(source="track.track_name")
    member_count = serializers.IntegerField()
    lead_user = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    @staticmethod
    def _read(obj, attr, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def get_lead_user(self, obj):
        lead_user_id = self._read(obj, "lead_user_id")
        if lead_user_id is None:
            return None
        return DashboardGroupLeadUserSerializer(
            {
                "id": lead_user_id,
                "first_name": self._read(obj, "lead_first_name") or "",
                "last_name": self._read(obj, "lead_last_name") or "",
            }
        ).data

    def get_lead_name(self, obj):
        if self._read(obj, "lead_user_id") is None:
            return None
        first = (self._read(obj, "lead_first_name") or "").strip()
        last = (self._read(obj, "lead_last_name") or "").strip()
        full = " ".join(part for part in (first, last) if part)
        return full or None

    def get_status(self, obj):
        return "active" if self._read(obj, "deleted_at") is None else "deleted"


class GroupsPreviewQuerySerializer(serializers.Serializer):
    """Validates query parameters for GET /dashboard/v1/groups-preview/"""
    mine = serializers.BooleanField(default=False)
    track_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)


class GroupsPreviewResponseSerializer(serializers.Serializer):
    """Envelope for the paginated groups-preview response."""
    count = serializers.IntegerField()
    next = serializers.IntegerField(allow_null=True)
    previous = serializers.IntegerField(allow_null=True)
    results = DashboardGroupPreviewSerializer(many=True)