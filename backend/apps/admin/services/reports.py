import csv
from datetime import timedelta, timezone as datetime_timezone

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.admin.services.analytics import _utc_date_range_filter
from apps.admin.services.page_reports import build_page_report
from apps.announcements.models import AnnouncementDelivery
from apps.audit.models import AuditLog
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import StudentProfile, User, UserInterest


REPORT_HEADERS = {
    "participants": ("category", "count", "percentage"),
    "permission": (
        "region",
        "total_students",
        "permission_granted",
        "permission_not_granted",
        "permission_rate",
    ),
    "login_activity": (
        "period_start",
        "period_end",
        "login_count",
        "unique_logged_in_users",
    ),
    "announcement_delivery": (
        "announcement_id",
        "title",
        "sent_at",
        "success_count",
        "failure_count",
        "delivery_rate",
    ),
}

_RANGE_DAYS = {"24h": 1, "7d": 7, "14d": 14}
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def build_report(params):
    report = params["report"]
    if report in {"overview", "users", "groups", "messages"}:
        return build_page_report(params)
    rows = {
        "participants": _participant_rows,
        "permission": _permission_rows,
        "login_activity": _login_rows,
        "announcement_delivery": _announcement_rows,
    }[report](params)
    return REPORT_HEADERS[report], rows, f"{report}-{timezone.now():%Y-%m-%d}.csv"


def stream_csv(headers, rows):
    writer = csv.writer(_Echo(), lineterminator="\r\n")
    yield "\ufeff"
    if headers:
        yield writer.writerow(headers)
    for row in rows:
        yield writer.writerow(_safe_csv_value(value) for value in row)


class _Echo:
    def write(self, value):
        return value


def _safe_csv_value(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _filtered_users(params):
    users = User.objects.all()
    now = timezone.now()
    if role := params.get("role"):
        users = users.filter(
            Q(roleassignmenthistory__role__role_name__iexact=role)
            & Q(roleassignmenthistory__valid_from__lte=now)
            & (
                Q(roleassignmenthistory__valid_to__isnull=True)
                | Q(roleassignmenthistory__valid_to__gte=now)
            )
        )
    if status := params.get("status"):
        users = users.filter(account_status=status)
    if country_id := params.get("country_id"):
        users = users.filter(country_id=country_id)
    if state_id := params.get("state_id"):
        users = users.filter(state_id=state_id)
    if interest := params.get("interest"):
        users = users.filter(userinterest__interest__interest_desc__iexact=interest)
    if params["report"] == "participants":
        if start := params.get("start_date"):
            users = users.filter(date_joined__date__gte=start)
        if end := params.get("end_date"):
            users = users.filter(date_joined__date__lte=end)
    return users.distinct()


def _participant_rows(params):
    users = _filtered_users(params)
    total = users.count()
    if not total:
        return []

    group_by = params["group_by"]
    if group_by == "role":
        now = timezone.now()
        active_roles = RoleAssignmentHistory.objects.filter(
            user_id__in=users.values("id"),
            valid_from__lte=now,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        counts = [
            (row["role__role_name"] or "Unspecified", row["count"])
            for row in active_roles.values("role__role_name").annotate(
                count=Count("user_id", distinct=True)
            )
        ]
        unspecified = users.exclude(
            id__in=active_roles.values("user_id")
        ).count()
        if unspecified:
            counts.append(("Unspecified", unspecified))
        counts = [(_display_enum(label), count) for label, count in counts]
    elif group_by == "interest":
        interests = UserInterest.objects.filter(user_id__in=users.values("id"))
        counts = [
            (row["interest__interest_desc"] or "Unspecified", row["count"])
            for row in interests.values("interest__interest_desc").annotate(
                count=Count("user_id", distinct=True)
            )
        ]
        unspecified = users.exclude(id__in=interests.values("user_id")).count()
        if unspecified:
            counts.append(("Unspecified", unspecified))
    else:
        field = {
            "status": "account_status",
            "country": "country__country_name",
            "state": "state__state_name",
        }[group_by]
        counts = [
            (row[field] or "Unspecified", row["count"])
            for row in users.values(field).annotate(count=Count("id", distinct=True))
        ]
        if group_by == "status":
            counts = [(_display_enum(label), count) for label, count in counts]

    return [
        (category, count, f"{count * 100 / total:.2f}")
        for category, count in sorted(counts, key=lambda item: item[0].casefold())
    ]


def _permission_rows(params):
    profiles = StudentProfile.objects.filter(
        user_id__in=_filtered_users(params).values("id")
    )
    if permission := params.get("permission"):
        profiles = profiles.filter(has_join_permission=permission == "granted")

    group_by = params["group_by"]
    field = {
        "none": None,
        "country": "user__country__country_name",
        "state": "user__state__state_name",
    }[group_by]
    aggregate = {
        "total": Count("pk"),
        "granted": Count("pk", filter=Q(has_join_permission=True)),
        "not_granted": Count("pk", filter=Q(has_join_permission=False)),
    }
    if field:
        values = profiles.values(field).annotate(**aggregate)
    else:
        summary = profiles.aggregate(**aggregate)
        values = [summary] if summary["total"] else []
    rows = []
    for value in values:
        total = value["total"]
        region = (value.get(field) if field else "All") or "Unspecified"
        rows.append(
            (
                region,
                total,
                value["granted"],
                value["not_granted"],
                f"{value['granted'] * 100 / total:.2f}" if total else "0.00",
            )
        )
    return sorted(rows, key=lambda row: row[0].casefold())


def _login_rows(params):
    start, end = _date_bounds(params)
    events = (
        AuditLog.objects.filter(
            action=AuditLog.ActionChoices.LOGIN,
            actor_user_id__in=_filtered_users(params).values("id"),
        )
        .filter(_utc_date_range_filter("created_at", start_date=start, end_date=end))
        .annotate(day=TruncDate("created_at", tzinfo=datetime_timezone.utc))
        .values("day")
        .annotate(
            login_count=Count("id"),
            unique_users=Count("actor_user_id", distinct=True),
        )
    )
    counts = {row["day"]: row for row in events}
    rows = []
    day = start
    while day <= end:
        value = counts.get(day, {})
        rows.append(
            (
                day.isoformat(),
                (day + timedelta(days=1)).isoformat(),
                value.get("login_count", 0),
                value.get("unique_users", 0),
            )
        )
        day += timedelta(days=1)
    return rows


def _announcement_rows(params):
    deliveries = AnnouncementDelivery.objects.select_related("announcement")
    if params.get("range") or params.get("start_date"):
        start, end = _date_bounds(params)
        deliveries = deliveries.filter(
            _utc_date_range_filter("started_at", start_date=start, end_date=end)
        )
    if delivery_status := params.get("delivery_status"):
        deliveries = deliveries.filter(status=delivery_status)

    def rows():
        for delivery in deliveries.order_by("started_at", "id").iterator(
            chunk_size=2000
        ):
            sent_at = delivery.completed_at or delivery.started_at
            attempted = delivery.success_count + delivery.failure_count
            yield (
                delivery.announcement_id,
                delivery.announcement.title,
                sent_at.isoformat(),
                delivery.success_count,
                delivery.failure_count,
                f"{delivery.success_count * 100 / attempted:.2f}"
                if attempted
                else "0.00",
            )

    return rows()


def _date_bounds(params):
    if params.get("start_date"):
        return params["start_date"], params["end_date"]
    days = _RANGE_DAYS[params.get("range", "7d")]
    end = timezone.now().date()
    return end - timedelta(days=days - 1), end


def _display_enum(value):
    return value.replace("_", " ").title()
