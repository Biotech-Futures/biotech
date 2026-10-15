"""Validation for read-only admin analytics endpoints."""

from datetime import date, timedelta

from rest_framework import serializers

from apps.admin.services.user import ROLES


class AnalyticsDateRangeSerializer(serializers.Serializer):
    start = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%d"],
        help_text="Include records on or after this date (YYYY-MM-DD).",
        error_messages={"invalid": "start must be an ISO date (YYYY-MM-DD)."},
    )
    end = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%d"],
        help_text="Include records on or before this date (YYYY-MM-DD).",
        error_messages={"invalid": "end must be an ISO date (YYYY-MM-DD)."},
    )

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")
        if start and end and end < start:
            raise serializers.ValidationError({"end": "end must be on or after start."})
        return attrs


class ResourceAnalyticsDateRangeSerializer(AnalyticsDateRangeSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start"].help_text = (
            "Include resource interactions on or after this date (YYYY-MM-DD)."
        )
        self.fields["end"].help_text = (
            "Include resource interactions on or before this date (YYYY-MM-DD)."
        )


class AnalyticsQueryRangeSerializer(serializers.Serializer):
    start = serializers.DateField(allow_null=True)
    end = serializers.DateField(allow_null=True)


class GroupMessageCountSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    message_count = serializers.IntegerField(min_value=0)


class UserMessageCountSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField(allow_null=True)
    message_count = serializers.IntegerField(min_value=0)


class DailyMessageCountSerializer(serializers.Serializer):
    date = serializers.DateField()
    message_count = serializers.IntegerField(min_value=0)


class GroupDailyMessageCountSerializer(DailyMessageCountSerializer):
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()


class UserGroupDailyMessageCountSerializer(GroupDailyMessageCountSerializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()


class MentorDailyActivitySerializer(serializers.Serializer):
    mentor_id = serializers.IntegerField()
    date = serializers.DateField()
    messages = serializers.IntegerField(min_value=0)
    logins = serializers.IntegerField(min_value=0)


class GroupActivityAnalyticsDataSerializer(serializers.Serializer):
    mentor_activity_by_day = MentorDailyActivitySerializer(many=True)
    messages_by_group = GroupMessageCountSerializer(many=True)
    messages_by_user = UserMessageCountSerializer(many=True)
    messages_by_day = DailyMessageCountSerializer(many=True)
    messages_by_group_by_day = GroupDailyMessageCountSerializer(many=True)
    messages_by_user_by_group_by_day = UserGroupDailyMessageCountSerializer(many=True)
    mentor_count = serializers.IntegerField(min_value=0)
    student_count = serializers.IntegerField(min_value=0)
    students_per_mentor = serializers.FloatField(allow_null=True)
    query_range = AnalyticsQueryRangeSerializer()


class GroupActivityAnalyticsResponseSerializer(serializers.Serializer):
    msg = serializers.CharField()
    data = GroupActivityAnalyticsDataSerializer()


class LoginActivityCountSerializer(serializers.Serializer):
    students = serializers.IntegerField(min_value=0)
    mentors = serializers.IntegerField(min_value=0)
    supervisors = serializers.IntegerField(min_value=0)
    total = serializers.IntegerField(min_value=0)


class DailyLoginActivitySerializer(LoginActivityCountSerializer):
    date = serializers.DateField()


class YearlyLoginActivitySerializer(LoginActivityCountSerializer):
    year = serializers.IntegerField(min_value=1, max_value=9999)


class LoginActivityWindowsSerializer(serializers.Serializer):
    daily = serializers.IntegerField(min_value=0)
    weekly = serializers.IntegerField(min_value=0)
    monthly = serializers.IntegerField(min_value=0)


class LoginActivityAnalyticsDataSerializer(serializers.Serializer):
    by_day = DailyLoginActivitySerializer(many=True)
    by_year = YearlyLoginActivitySerializer(many=True)
    active_users = LoginActivityWindowsSerializer()
    latest_activity_date = serializers.DateField(allow_null=True)
    query_range = AnalyticsQueryRangeSerializer()


class LoginActivityAnalyticsResponseSerializer(serializers.Serializer):
    msg = serializers.CharField()
    data = LoginActivityAnalyticsDataSerializer()


class DailyResourceClickCountSerializer(serializers.Serializer):
    date = serializers.DateField()
    click_count = serializers.IntegerField(min_value=0)


class ResourceClickCountSerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    resource_name = serializers.CharField()
    click_count = serializers.IntegerField(min_value=0)
    unique_users = serializers.IntegerField(min_value=0)


class ResourceCategoryClickCountSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)
    click_count = serializers.IntegerField(min_value=0)


class ResourceAnalyticsDataSerializer(serializers.Serializer):
    total_clicks = serializers.IntegerField(min_value=0)
    unique_users = serializers.IntegerField(min_value=0)
    active_resources = serializers.IntegerField(min_value=0)
    clicks_by_day = DailyResourceClickCountSerializer(many=True)
    top_resources = ResourceClickCountSerializer(many=True)
    clicks_by_category = ResourceCategoryClickCountSerializer(many=True)
    query_range = AnalyticsQueryRangeSerializer()


class ResourceAnalyticsResponseSerializer(serializers.Serializer):
    msg = serializers.CharField()
    data = ResourceAnalyticsDataSerializer()


class EmailDeliveryTotalsSerializer(serializers.Serializer):
    attempted = serializers.IntegerField(min_value=0)
    delivered = serializers.IntegerField(min_value=0)
    failed = serializers.IntegerField(min_value=0)
    delivery_runs = serializers.IntegerField(min_value=0)


class EmailDeliveryPeriodSerializer(serializers.Serializer):
    attempted = serializers.IntegerField(min_value=0)
    delivered = serializers.IntegerField(min_value=0)
    failed = serializers.IntegerField(min_value=0)


class EmailDeliveryHourlySerializer(EmailDeliveryPeriodSerializer):
    hour = serializers.DateTimeField()


class EmailDeliveryDailySerializer(EmailDeliveryPeriodSerializer):
    date = serializers.DateField()


class EmailMailboxAnalyticsSerializer(serializers.Serializer):
    email = serializers.EmailField()
    quota_limit = serializers.IntegerField(min_value=0)
    totals = EmailDeliveryTotalsSerializer()
    hourly = EmailDeliveryHourlySerializer(many=True)
    daily = EmailDeliveryDailySerializer(many=True)


class EmailDeliveryStatusByRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("Student", "Mentor", "Supervisor"))
    attempted = serializers.IntegerField(min_value=0)
    delivered = serializers.IntegerField(min_value=0)
    opened = serializers.IntegerField(min_value=0, allow_null=True)
    failed = serializers.IntegerField(min_value=0)
    tracked_deliveries = serializers.IntegerField(min_value=0)


class EmailRoleAttributionSerializer(serializers.Serializer):
    basis = serializers.CharField()
    available = serializers.BooleanField()
    complete = serializers.BooleanField()
    tracked_delivery_runs = serializers.IntegerField(min_value=0)
    unattributed_delivery_runs = serializers.IntegerField(min_value=0)
    tracked_attempted = serializers.IntegerField(min_value=0)
    unattributed_attempted = serializers.IntegerField(min_value=0)
    tracked_delivered = serializers.IntegerField(min_value=0)
    unattributed_delivered = serializers.IntegerField(min_value=0)
    tracked_failed = serializers.IntegerField(min_value=0)
    unattributed_failed = serializers.IntegerField(min_value=0)


class RecentEmailDeliverySerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    announcement_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField()
    started_at = serializers.DateTimeField()
    status = serializers.CharField()
    recipient_count = serializers.IntegerField(min_value=0)
    success_count = serializers.IntegerField(min_value=0)
    failure_count = serializers.IntegerField(min_value=0)
    initiated_by_name = serializers.CharField(allow_blank=True)
    initiated_by_email = serializers.EmailField(allow_blank=True)


class EmailDeliveryAnalyticsDataSerializer(serializers.Serializer):
    snapshot_at = serializers.DateTimeField()
    mailboxes = EmailMailboxAnalyticsSerializer(many=True)
    mailbox = serializers.EmailField()
    quota_limit = serializers.IntegerField(min_value=0)
    totals = EmailDeliveryTotalsSerializer()
    hourly = EmailDeliveryHourlySerializer(many=True)
    daily = EmailDeliveryDailySerializer(many=True)
    status_by_role = EmailDeliveryStatusByRoleSerializer(many=True)
    role_attribution = EmailRoleAttributionSerializer()
    recent_deliveries = RecentEmailDeliverySerializer(many=True)


class EmailDeliveryAnalyticsResponseSerializer(serializers.Serializer):
    msg = serializers.CharField()
    data = EmailDeliveryAnalyticsDataSerializer()


class ReportExportQuerySerializer(serializers.Serializer):
    REPORTS = (
        "participants",
        "permission",
        "login_activity",
        "announcement_delivery",
        "overview",
        "users",
        "groups",
        "messages",
    )
    GROUPS = ("role", "status", "interest", "country", "state", "none")
    RANGES = ("24h", "7d", "14d")

    report = serializers.ChoiceField(choices=REPORTS)
    format = serializers.ChoiceField(choices=("csv",), default="csv")
    group_by = serializers.ChoiceField(choices=GROUPS, required=False)
    range = serializers.ChoiceField(choices=RANGES, required=False)
    start_date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    end_date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    year = serializers.IntegerField(required=False, min_value=1, max_value=9999)
    registration_period = serializers.ChoiceField(
        choices=("day", "week", "month", "year"), required=False
    )
    interval = serializers.ChoiceField(
        choices=("day", "week", "month"), required=False, default="day"
    )
    mode = serializers.ChoiceField(choices=("groups", "users"), required=False)
    group_id = serializers.IntegerField(required=False, min_value=1)
    user_role = serializers.ChoiceField(
        choices=("all", "Student", "Mentor", "Supervisor", "Unavailable"),
        required=False,
    )
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    sort_by = serializers.ChoiceField(
        choices=("value", "avgPerDay", "last7Days", "share"), required=False
    )
    sort_order = serializers.ChoiceField(choices=("asc", "desc"), required=False)
    anchor_date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    show_all_details = serializers.BooleanField(required=False, default=False)
    role = serializers.ChoiceField(choices=ROLES, required=False)
    status = serializers.ChoiceField(
        choices=("invited", "pending", "active", "suspended", "deactivated"),
        required=False,
    )
    country_id = serializers.IntegerField(required=False, min_value=1)
    state_id = serializers.IntegerField(required=False, min_value=1)
    interest = serializers.CharField(required=False, max_length=255)
    permission = serializers.ChoiceField(choices=("granted", "not_granted"), required=False)
    delivery_status = serializers.ChoiceField(
        choices=("success", "partial", "failed"), required=False
    )

    _allowed_by_report = {
        "participants": {
            "report", "format", "group_by", "role", "status", "country_id",
            "state_id", "interest", "start_date", "end_date",
        },
        "permission": {
            "report", "format", "group_by", "status", "country_id", "state_id",
            "permission",
        },
        "login_activity": {
            "report", "format", "range", "start_date", "end_date", "role",
            "status", "country_id", "state_id",
        },
        "announcement_delivery": {
            "report", "format", "range", "start_date", "end_date", "delivery_status",
        },
        "overview": {"report", "format", "year", "registration_period"},
        "users": {"report", "format", "year"},
        "groups": {"report", "format", "year"},
        "messages": {
            "report", "format", "start_date", "end_date", "interval", "mode",
            "group_id", "user_role", "search", "sort_by", "sort_order",
            "anchor_date", "show_all_details",
        },
    }

    def validate(self, attrs):
        report = attrs["report"]
        supplied = set(self.initial_data.keys())
        unsupported = supplied - self._allowed_by_report[report]
        if unsupported:
            raise serializers.ValidationError(
                {name: f"{name} is not supported for {report}." for name in unsupported}
            )

        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        if attrs.get("range") and (start or end):
            raise serializers.ValidationError(
                {"range": "range cannot be combined with start_date or end_date."}
            )
        if report in {"login_activity", "announcement_delivery"}:
            if bool(start) != bool(end):
                missing = "end_date" if start else "start_date"
                raise serializers.ValidationError(
                    {missing: f"{missing} is required for a custom date range."}
                )
            if start and end and (end - start).days >= 3660:
                raise serializers.ValidationError(
                    {"end_date": "Date range must be no longer than 3660 days."}
                )
            if report == "login_activity" and end == date.max:
                raise serializers.ValidationError(
                    {"end_date": "The final calendar day cannot be a login period end."}
                )
        if report in {"overview", "users", "groups"} and "year" not in attrs:
            raise serializers.ValidationError({"year": "year is required."})
        if report == "messages":
            if not start or not end:
                raise serializers.ValidationError(
                    {"start_date": "start_date and end_date are required."}
                )
            if (attrs.get("anchor_date") or end) < date.min + timedelta(days=6):
                raise serializers.ValidationError(
                    {"anchor_date": "anchor_date is outside the supported range."}
                )

        allowed_groups = {
            "participants": {"role", "status", "interest", "country", "state"},
            "permission": {"none", "country", "state"},
        }
        group_by = attrs.get("group_by")
        if group_by and group_by not in allowed_groups.get(report, set()):
            raise serializers.ValidationError(
                {"group_by": f"group_by={group_by} is not supported for {report}."}
            )
        if report == "participants":
            attrs.setdefault("group_by", "role")
        elif report == "permission":
            attrs.setdefault("group_by", "state")
        elif report == "login_activity" and not (start and end):
            attrs.setdefault("range", "7d")
        return attrs
