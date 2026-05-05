from rest_framework import serializers

from .services import MENTOR_MEMBERSHIPS_ATTR


class ProgressQuerySerializer(serializers.Serializer):
    group_id = serializers.IntegerField(required=False, allow_null=True)


class GroupsPreviewQuerySerializer(serializers.Serializer):
    mine = serializers.BooleanField(required=False, default=False)
    track_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


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


class DashboardLeadUserSerializer(serializers.Serializer):
    """Compact projection of the mentor (lead) user embedded in the group preview."""

    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class DashboardGroupPreviewSerializer(serializers.Serializer):
    """
    Flattened, deeply-associated group projection used by the dashboard
    groups-preview endpoint.

    Backed by ``services.get_groups_preview`` which returns an annotated
    queryset (``member_count`` annotation, mentor memberships prefetched
    onto ``MENTOR_MEMBERSHIPS_ATTR``), so this serializer never triggers
    extra queries per row.
    """

    id = serializers.IntegerField()
    group_name = serializers.CharField()
    track_id = serializers.IntegerField()
    track_name = serializers.CharField(source="track.track_name")
    member_count = serializers.IntegerField()
    lead_user = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    @staticmethod
    def _lead_user(group):
        memberships = getattr(group, MENTOR_MEMBERSHIPS_ATTR, None) or []
        return memberships[0].user if memberships else None

    def get_lead_user(self, group):
        user = self._lead_user(group)
        return DashboardLeadUserSerializer(user).data if user else None

    def get_lead_name(self, group):
        user = self._lead_user(group)
        return (user.get_full_name() or user.email) if user else None

    def get_status(self, group):
        if group.deleted_at is not None:
            return "deleted"
        return "active" if self._lead_user(group) else "inactive"
