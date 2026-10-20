from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, Window
from django.db.models.functions import Coalesce, RowNumber, TruncDate, TruncHour
from django.utils import timezone

from apps.announcements.models import (
    Announcement,
    AnnouncementAudience,
    AnnouncementDelivery,
)
from apps.audit.models import AuditLog
from apps.chat.models import Messages
from apps.groups.models import GroupMembership, Groups, group_name_sort_key
from apps.resources.models import ResourceAccessEvent, RoleAssignmentHistory
from apps.services.email_registry import get_email_type, is_known_email_type
from apps.services.models import EmailDeliveryMetric, EmailDeliveryRecipient
from apps.users.models import User


SUPPORTED_ANALYTICS_ROLES = {
    "student": "Student",
    "mentor": "Mentor",
    "supervisor": "Supervisor",
}


def _utc_date_range_filter(
    field_name: str, *, start_date: date | None, end_date: date | None
) -> Q:
    """Build an index-friendly inclusive UTC calendar-date filter.

    Comparing the timestamp directly avoids PostgreSQL casting every row to a
    date.  The exclusive next-day upper bound also includes every timestamp on
    ``end_date`` without relying on a database-specific end-of-day precision.
    """

    filters = {}
    if start_date is not None:
        filters[f"{field_name}__gte"] = datetime.combine(
            start_date,
            time.min,
            tzinfo=datetime_timezone.utc,
        )
    if end_date is not None:
        if end_date < date.max:
            filters[f"{field_name}__lt"] = datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=datetime_timezone.utc,
            )
        else:
            filters[f"{field_name}__lte"] = datetime.max.replace(
                tzinfo=datetime_timezone.utc
            )
    return Q(**filters)


def get_group_activity_analytics(
    *, start_date: date | None = None, end_date: date | None = None
) -> dict:
    """Aggregate group activity, optionally within an inclusive date range.

    Only active groups, active memberships, and non-deleted messages contribute.
    Group and user rows with zero messages remain visible so inactivity is not
    hidden by the aggregation. Date bounds apply to message counts. Yearly group
    sizes are reconstructed from group and membership join/leave timestamps, so
    they do not depend on a separate snapshot table.
    """

    messages_in_range = Messages.objects.filter(deleted_at__isnull=True).filter(
        _utc_date_range_filter(
            "sent_at",
            start_date=start_date,
            end_date=end_date,
        )
    )
    group_message_counts = (
        messages_in_range.filter(group_id=OuterRef("pk"))
        .order_by()
        .values("group_id")
        .annotate(total=Count("id"))
        .values("total")
    )

    messages_by_group = [
        {
            "group_id": row["id"],
            "group_name": row["group_name"],
            "message_count": row["message_count"],
        }
        for row in (
            Groups.objects.active()
            .annotate(
                message_count=Coalesce(
                    Subquery(group_message_counts, output_field=IntegerField()),
                    Value(0),
                ),
                group_name_key=group_name_sort_key(),
            )
            .order_by("group_name_key", "id")
            .values("id", "group_name", "message_count")
        )
    ]

    active_member_user_ids = GroupMembership.objects.filter(
        group__deleted_at__isnull=True,
        left_at__isnull=True,
    ).values("user_id")
    user_message_counts = (
        messages_in_range.filter(
            sender_user_id=OuterRef("pk"),
            group__deleted_at__isnull=True,
        )
        .order_by()
        .values("sender_user_id")
        .annotate(total=Count("id"))
        .values("total")
    )

    messages_by_user = [
        {
            "user_id": row["id"],
            "name": (
                f"{row['first_name']} {row['last_name']}".strip()
                or f"User {row['id']}"
            ),
            "message_count": row["message_count"],
        }
        for row in (
            User.objects.filter(pk__in=Subquery(active_member_user_ids))
            .annotate(
                message_count=Coalesce(
                    Subquery(user_message_counts, output_field=IntegerField()),
                    Value(0),
                )
            )
            .order_by("first_name", "last_name", "id")
            .values("id", "first_name", "last_name", "message_count")
        )
    ]

    daily_messages = messages_in_range.filter(group__deleted_at__isnull=True)

    messages_by_day = [
        {
            "date": row["date"],
            "message_count": row["message_count"],
        }
        for row in (
            daily_messages.annotate(
                date=TruncDate("sent_at", tzinfo=datetime_timezone.utc)
            )
            .values("date")
            .annotate(message_count=Count("id"))
            .order_by("date")
        )
    ]

    messages_by_group_by_day = [
        {
            "date": row["date"],
            "group_id": row["group_id"],
            "group_name": row["group__group_name"],
            "message_count": row["message_count"],
        }
        for row in (
            daily_messages.annotate(
                date=TruncDate("sent_at", tzinfo=datetime_timezone.utc)
            )
            .values("date", "group_id", "group__group_name")
            .annotate(message_count=Count("id"))
            .order_by("date", "group_id")
        )
    ]

    messages_by_user_by_group_by_day = [
        {
            "date": row["date"],
            "user_id": row["sender_user_id"],
            "name": (
                f"{row['sender_user__first_name']} "
                f"{row['sender_user__last_name']}"
            ).strip()
            or f"User {row['sender_user_id']}",
            "group_id": row["group_id"],
            "group_name": row["group__group_name"],
            "message_count": row["message_count"],
        }
        for row in (
            daily_messages.annotate(
                date=TruncDate("sent_at", tzinfo=datetime_timezone.utc)
            )
            .values(
                "date",
                "sender_user_id",
                "sender_user__first_name",
                "sender_user__last_name",
                "group_id",
                "group__group_name",
            )
            .annotate(message_count=Count("id"))
            .order_by("date", "group_id", "sender_user_id")
        )
    ]

    mentor_ids = User.objects.filter(mentorprofile__isnull=False).values("pk")
    mentor_events = {}
    for row in daily_messages.filter(sender_user_id__in=mentor_ids).annotate(
        date=TruncDate("sent_at", tzinfo=datetime_timezone.utc)
    ).values("sender_user_id", "date").annotate(total=Count("id")).order_by():
        key = (row["sender_user_id"], row["date"])
        mentor_events[key] = {"mentor_id": key[0], "date": key[1],
                              "messages": row["total"], "logins": 0}
    login_events = AuditLog.objects.filter(
        action=AuditLog.ActionChoices.LOGIN, entity_type="user",
        actor_user_id__in=mentor_ids,
    ).filter(_utc_date_range_filter("created_at", start_date=start_date, end_date=end_date))
    for row in login_events.annotate(
        date=TruncDate("created_at", tzinfo=datetime_timezone.utc)
    ).values("actor_user_id", "date").annotate(total=Count("id")).order_by():
        key = (row["actor_user_id"], row["date"])
        event = mentor_events.setdefault(key, {"mentor_id": key[0], "date": key[1],
                                               "messages": 0, "logins": 0})
        event["logins"] = row["total"]

    active_memberships = GroupMembership.objects.filter(
        group__deleted_at__isnull=True,
        left_at__isnull=True,
    )
    mentor_count = (
        active_memberships.filter(
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR
        )
        .values("user_id")
        .distinct()
        .count()
    )
    student_count = (
        active_memberships.filter(
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT
        )
        .values("user_id")
        .distinct()
        .count()
    )
    mentor_assignments = active_memberships.filter(
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR
    )
    mentor_assignment_count = mentor_assignments.count()
    mentored_group_ids = mentor_assignments.values("group_id")
    students_in_mentored_groups = active_memberships.filter(
        membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        group_id__in=mentored_group_ids,
    ).count()

    comparison_year = (end_date or timezone.localdate()).year
    average_group_size_by_year = []
    group_summary_by_year = []
    for year in (comparison_year - 1, comparison_year):
        period_end = datetime(
            year,
            12,
            31,
            23,
            59,
            59,
            999999,
            tzinfo=datetime_timezone.utc,
        )
        groups_at_year_end = Groups.objects.filter(created_at__lte=period_end).filter(
            Q(deleted_at__isnull=True) | Q(deleted_at__gt=period_end)
        )
        group_count = groups_at_year_end.count()
        memberships_at_year_end = GroupMembership.objects.filter(
            group__in=groups_at_year_end,
            joined_at__lte=period_end,
        ).filter(Q(left_at__isnull=True) | Q(left_at__gt=period_end))
        student_memberships_at_year_end = memberships_at_year_end.filter(
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        mentor_memberships_at_year_end = memberships_at_year_end.filter(
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        student_memberships = student_memberships_at_year_end.count()
        historical_student_count = (
            student_memberships_at_year_end.values("user_id").distinct().count()
        )
        historical_mentor_count = (
            mentor_memberships_at_year_end.values("user_id").distinct().count()
        )
        groups_with_mentor = (
            mentor_memberships_at_year_end.values("group_id").distinct().count()
        )
        historical_mentor_assignments = mentor_memberships_at_year_end.count()
        historical_students_in_mentored_groups = (
            student_memberships_at_year_end.filter(
                group_id__in=mentor_memberships_at_year_end.values("group_id")
            ).count()
        )
        average_group_size_by_year.append(
            {
                "year": year,
                "group_count": group_count,
                "student_memberships": student_memberships,
                "average_group_size": (
                    round(student_memberships / group_count, 1) if group_count else 0
                ),
            }
        )
        group_summary_by_year.append(
            {
                "year": year,
                "group_count": group_count,
                "groups_with_mentor": groups_with_mentor,
                "groups_without_mentor": max(group_count - groups_with_mentor, 0),
                "mentor_count": historical_mentor_count,
                "student_count": historical_student_count,
                "students_per_mentor": (
                    round(
                        historical_students_in_mentored_groups
                        / historical_mentor_assignments,
                        2,
                    )
                    if historical_mentor_assignments
                    else None
                ),
            }
        )

    return {
        "messages_by_group": messages_by_group,
        "messages_by_user": messages_by_user,
        "messages_by_day": messages_by_day,
        "messages_by_group_by_day": messages_by_group_by_day,
        "messages_by_user_by_group_by_day": messages_by_user_by_group_by_day,
        "mentor_activity_by_day": sorted(mentor_events.values(), key=lambda row: (row["date"], row["mentor_id"])),
        "mentor_count": mentor_count,
        "student_count": student_count,
        "students_per_mentor": (
            round(students_in_mentored_groups / mentor_assignment_count, 2)
            if mentor_assignment_count
            else None
        ),
        "average_group_size_by_year": average_group_size_by_year,
        "group_summary_by_year": group_summary_by_year,
        "query_range": {"start": start_date, "end": end_date},
    }


def get_login_activity_analytics(
    *, start_date: date | None = None, end_date: date | None = None
) -> dict:
    """Return real, successful login activity grouped by UTC date and role.

    The dashboard compares current role populations, so historical login rows
    are classified using each user's current active role. A user is counted at
    most once per UTC day and once per reporting year, regardless of how many
    sessions they started during that period.
    """

    events = AuditLog.objects.filter(
        action=AuditLog.ActionChoices.LOGIN,
        entity_type="user",
        actor_user_id__isnull=False,
    ).filter(
        _utc_date_range_filter(
            "created_at",
            start_date=start_date,
            end_date=end_date,
        )
    )

    user_ids = list(events.values_list("actor_user_id", flat=True).distinct())
    now = timezone.now()
    role_by_user: dict[int, str] = {}
    for row in (
        RoleAssignmentHistory.objects.filter(
            user_id__in=user_ids,
            valid_from__lte=now,
        )
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        .select_related("role")
        .order_by("user_id", "-valid_from", "-id")
    ):
        role_name = (row.role.role_name if row.role else "").lower()
        role = SUPPORTED_ANALYTICS_ROLES.get(role_name)
        if role:
            role_by_user.setdefault(row.user_id, role)

    daily_users: dict[date, dict[str, set[int]]] = defaultdict(
        lambda: {role: set() for role in SUPPORTED_ANALYTICS_ROLES.values()}
    )
    yearly_users: dict[int, dict[str, set[int]]] = defaultdict(
        lambda: {role: set() for role in SUPPORTED_ANALYTICS_ROLES.values()}
    )
    for row in (
        events.annotate(date=TruncDate("created_at", tzinfo=datetime_timezone.utc))
        .values("actor_user_id", "date")
        .distinct()
        .order_by("date", "actor_user_id")
    ):
        role = role_by_user.get(row["actor_user_id"])
        if not role:
            continue
        daily_users[row["date"]][role].add(row["actor_user_id"])
        yearly_users[row["date"].year][role].add(row["actor_user_id"])

    def counts(role_sets: dict[str, set[int]]) -> dict[str, int]:
        result = {
            "students": len(role_sets["Student"]),
            "mentors": len(role_sets["Mentor"]),
            "supervisors": len(role_sets["Supervisor"]),
        }
        result["total"] = sum(result.values())
        return result

    by_day = [
        {"date": day, **counts(role_sets)}
        for day, role_sets in sorted(daily_users.items())
    ]
    by_year = [
        {"year": year, **counts(role_sets)}
        for year, role_sets in sorted(yearly_users.items())
    ]

    latest_activity_date = by_day[-1]["date"] if by_day else None
    anchor_date = end_date or latest_activity_date
    windows = {"daily": 0, "weekly": 0, "monthly": 0}
    window_comparisons = {
        "daily": {"current": 0, "previous": 0},
        "weekly": {"current": 0, "previous": 0},
        "monthly": {"current": 0, "previous": 0},
    }
    if anchor_date is not None:
        def unique_users_between(lower: date, upper: date) -> int:
            return (
                events.filter(
                    created_at__gte=datetime.combine(
                        lower, time.min, tzinfo=datetime_timezone.utc
                    ),
                    created_at__lt=datetime.combine(
                        upper + timedelta(days=1),
                        time.min,
                        tzinfo=datetime_timezone.utc,
                    ),
                    actor_user_id__in=role_by_user,
                )
                .values("actor_user_id")
                .distinct()
                .count()
            )

        for key, days in (("daily", 1), ("weekly", 7), ("monthly", 30)):
            current_lower = anchor_date - timedelta(days=days - 1)
            previous_upper = current_lower - timedelta(days=1)
            previous_lower = previous_upper - timedelta(days=days - 1)
            current = unique_users_between(current_lower, anchor_date)
            previous = unique_users_between(previous_lower, previous_upper)
            windows[key] = current
            window_comparisons[key] = {
                "current": current,
                "previous": previous,
            }

    return {
        "by_day": by_day,
        "by_year": by_year,
        "active_users": windows,
        "active_user_comparison": window_comparisons,
        "latest_activity_date": latest_activity_date,
        "query_range": {"start": start_date, "end": end_date},
    }


def get_resource_analytics(
    *, start_date: date | None = None, end_date: date | None = None
) -> dict:
    """Count interactions, including soft-deleted resources, by current type.

    Date bounds and daily groups use the current Django timezone. Only dates
    and resources with events are returned; uncategorized events form one group.
    ``clicks_by_resource_by_day`` gives each resource's daily clicks and
    distinct users, so per-resource trends can be compared; daily distinct
    users cannot be summed into a period total.
    """
    events = ResourceAccessEvent.objects.all()
    if start_date is not None:
        events = events.filter(created_at__date__gte=start_date)
    if end_date is not None:
        events = events.filter(created_at__date__lte=end_date)

    totals = events.aggregate(
        total_clicks=Count("id"),
        unique_users=Count("user_id", distinct=True),
        active_resources=Count("resource_id", distinct=True),
    )
    clicks_by_day = list(
        events.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(click_count=Count("id"))
        .order_by("date")
    )
    top_resources = [
        {
            "resource_id": row["resource_id"],
            "resource_name": row["resource__name"],
            "click_count": row["click_count"],
            "unique_users": row["unique_users"],
        }
        for row in events.values("resource_id", "resource__name")
        .annotate(click_count=Count("id"), unique_users=Count("user_id", distinct=True))
        .order_by("-click_count", "resource_id")
    ]
    clicks_by_resource_by_day = [
        {
            "date": row["date"],
            "resource_id": row["resource_id"],
            "resource_name": row["resource__name"],
            "click_count": row["click_count"],
            "unique_users": row["unique_users"],
        }
        for row in events.annotate(date=TruncDate("created_at"))
        .values("date", "resource_id", "resource__name")
        .annotate(click_count=Count("id"), unique_users=Count("user_id", distinct=True))
        .order_by("date", "resource_id")
    ]
    clicks_by_category = [
        {
            "category_id": row["resource__type_id"],
            "category_name": row["resource__type__type_name"],
            "click_count": row["click_count"],
        }
        for row in events.values("resource__type_id", "resource__type__type_name")
        .annotate(click_count=Count("id"))
        .order_by("-click_count", F("resource__type_id").asc(nulls_last=True))
    ]
    return {
        **totals,
        "clicks_by_day": clicks_by_day,
        "top_resources": top_resources,
        "clicks_by_resource_by_day": clicks_by_resource_by_day,
        "clicks_by_category": clicks_by_category,
        "query_range": {"start": start_date, "end": end_date},
    }


# Kept per email type, so frequent sends (login codes) cannot push rarer ones
# (announcements) out of the list or out of its type filter.
RECENT_SENDS_PER_TYPE = 100


def _email_type_label(key: str) -> str:
    """System Emails name for a send type, or a readable form of its key."""
    if is_known_email_type(key):
        return get_email_type(key).name
    return key.replace("_", " ").replace("-", " ").strip().capitalize() or "Email"


def _recent_email_sends() -> list[dict]:
    """The latest ``RECENT_SENDS_PER_TYPE`` sends of each email type, newest first.

    ``EmailDeliveryMetric`` records one row per real send operation for system
    emails, announcements, chat digests and management bulk sends, so it is the
    one source that covers every type. Announcement sends are matched to their
    delivery row (recorded with the same start time) to show the title.
    """
    rows = list(
        EmailDeliveryMetric.objects.select_related("initiated_by")
        .annotate(
            type_rank=Window(
                RowNumber(),
                partition_by=[F("email_type")],
                order_by=[F("started_at").desc(), F("id").desc()],
            )
        )
        .filter(type_rank__lte=RECENT_SENDS_PER_TYPE)
        .order_by("-started_at", "-id")
    )
    recorded = dict(
        EmailDeliveryRecipient.objects.filter(metric_id__in=[row.id for row in rows])
        .values("metric_id")
        .annotate(total=Count("id"))
        .values_list("metric_id", "total")
    )
    return [
        {**send, "recipients_recorded": recorded.get(send["id"], 0)}
        for send in _send_rows(rows)
    ]


def _send_rows(rows) -> list[dict]:
    """``EmailDeliveryMetric`` rows as the Email Logs list them. Announcement
    sends are matched to their delivery row (recorded with the same start
    time) to show the title."""
    announcement_starts = [row.started_at for row in rows if row.email_type == "announcement"]
    announcements_by_start = {
        delivery.started_at: delivery
        for delivery in AnnouncementDelivery.objects.filter(
            started_at__in=announcement_starts
        ).select_related("announcement")
    } if announcement_starts else {}

    sends = []
    for row in rows:
        delivery = (
            announcements_by_start.get(row.started_at)
            if row.email_type == "announcement"
            else None
        )
        sends.append(
            {
                "id": row.id,
                "email_type": row.email_type,
                "email_type_label": _email_type_label(row.email_type),
                "title": delivery.announcement.title if delivery else None,
                "announcement_id": delivery.announcement_id if delivery else None,
                "source_mailbox": row.source_mailbox,
                "started_at": row.started_at.isoformat(),
                "status": row.status,
                "attempted": row.attempted_count,
                "delivered": row.delivered_count,
                "failed": row.failed_count,
                "initiated_by_name": (
                    f"{row.initiated_by.first_name} {row.initiated_by.last_name}".strip()
                    if row.initiated_by
                    else "System"
                ),
                "initiated_by_email": row.initiated_by.email if row.initiated_by else "",
            }
        )
    return sends


def _recipient_row(recipient: EmailDeliveryRecipient) -> dict:
    user = recipient.user
    return {
        "email": recipient.email,
        "user_id": recipient.user_id,
        "name": f"{user.first_name} {user.last_name}".strip() if user else "",
        "status": recipient.status,
        "reason": recipient.reason,
    }


def get_email_send_recipients(send_id: int) -> dict | None:
    """Everyone one send was addressed to, and whether it reached them.

    ``None`` when the send does not exist. A send made before recipients were
    recorded returns an empty list with ``recipients_recorded`` False.
    """
    metric = (
        EmailDeliveryMetric.objects.select_related("initiated_by")
        .filter(pk=send_id)
        .first()
    )
    if metric is None:
        return None
    recipients = [
        _recipient_row(recipient)
        for recipient in metric.recipients.select_related("user").order_by("email", "id")
    ]
    return {
        "send": _send_rows([metric])[0],
        "recipients_recorded": bool(recipients),
        "recipients": recipients,
    }


RECIPIENT_SEARCH_LIMIT = 200
RECIPIENT_SEARCH_MIN_LENGTH = 3


def find_email_sends_for_recipient(query: str) -> list[dict]:
    """Emails sent to the recipients matching ``query``, newest first.

    ``query`` matches part of a recipient address or of the name on the
    account it belongs to. Each result is one send to one matching recipient,
    with whether that send reached them.
    """
    terms = (query or "").strip()
    if len(terms) < RECIPIENT_SEARCH_MIN_LENGTH:
        return []
    name_match = Q()
    for word in terms.split():
        name_match &= Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word)
    matches = list(
        EmailDeliveryRecipient.objects.select_related("user", "metric", "metric__initiated_by")
        .filter(Q(email__icontains=terms) | name_match)
        .order_by("-metric__started_at", "-metric_id", "email")[:RECIPIENT_SEARCH_LIMIT]
    )
    sends = {send["id"]: send for send in _send_rows(list({m.metric_id: m.metric for m in matches}.values()))}
    return [
        {**sends[match.metric_id], "recipient": _recipient_row(match)}
        for match in matches
    ]


def get_email_delivery_analytics() -> dict:
    """Return email-delivery analytics for the configured sending mailboxes.

    Each persisted delivery is attributed to the mailbox that sent it. The
    rolling window is always the actual 24 hours ending at the current time.
    """

    primary_mailbox = settings.EMAIL_FROM_ADDRESS
    secondary_mailbox = settings.CONNECT_FROM_ADDRESS
    quota_limit = 3000

    zero_totals = {
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
        "delivery_runs": 0,
    }
    role_labels = {
        "student": "Student",
        "mentor": "Mentor",
        "supervisor": "Supervisor",
    }

    def empty_role_status() -> list[dict]:
        return [
            {
                "role": role_label,
                "attempted": 0,
                "delivered": 0,
                # Open/provider events are not persisted by the current schema.
                "opened": None,
                "failed": 0,
                "tracked_deliveries": 0,
            }
            for role_label in role_labels.values()
        ]

    def role_attribution(
        *,
        tracked_delivery_runs: int,
        unattributed_delivery_runs: int,
        tracked_attempted: int,
        unattributed_attempted: int,
        tracked_delivered: int,
        unattributed_delivered: int,
        tracked_failed: int,
        unattributed_failed: int,
    ) -> dict:
        """Describe coverage without claiming a send-time role snapshot.

        Announcement deliveries do not persist the audience or role that was
        resolved when the send occurred.  Role attribution is therefore only
        available for delivery runs whose announcement *currently* has one
        unambiguous supported role audience.  ``complete`` describes coverage
        under that limited basis, not historical certainty.
        """

        available = tracked_delivery_runs > 0
        return {
            "basis": "current_single_role_audience",
            "available": available,
            "complete": available and unattributed_delivery_runs == 0,
            "tracked_delivery_runs": tracked_delivery_runs,
            "unattributed_delivery_runs": unattributed_delivery_runs,
            "tracked_attempted": tracked_attempted,
            "unattributed_attempted": unattributed_attempted,
            "tracked_delivered": tracked_delivered,
            "unattributed_delivered": unattributed_delivered,
            "tracked_failed": tracked_failed,
            "unattributed_failed": unattributed_failed,
        }

    snapshot_at = timezone.now()

    if not EmailDeliveryMetric.objects.exists():
        empty_mailboxes = [
            {
                "email": primary_mailbox,
                "quota_limit": quota_limit,
                "totals": dict(zero_totals),
                "hourly": [],
                "daily": [],
            },
            {
                "email": secondary_mailbox,
                "quota_limit": quota_limit,
                "totals": dict(zero_totals),
                "hourly": [],
                "daily": [],
            },
        ]
        return {
            "snapshot_at": snapshot_at.isoformat(),
            "mailboxes": empty_mailboxes,
            # Legacy fields retained while frontend/backend branches converge.
            "mailbox": primary_mailbox,
            "quota_limit": quota_limit,
            "totals": dict(zero_totals),
            "hourly": [],
            "daily": [],
            "status_by_role": empty_role_status(),
            "recent_sends": [],
            "role_attribution": role_attribution(
                tracked_delivery_runs=0,
                unattributed_delivery_runs=0,
                tracked_attempted=0,
                unattributed_attempted=0,
                tracked_delivered=0,
                unattributed_delivered=0,
                tracked_failed=0,
                unattributed_failed=0,
            ),
            "recent_deliveries": [],
        }

    window_start = snapshot_at - timedelta(hours=24)
    metric_window = EmailDeliveryMetric.objects.filter(
        started_at__gt=window_start,
        started_at__lte=snapshot_at,
    )
    announcement_window = AnnouncementDelivery.objects.filter(
        started_at__gt=window_start,
        started_at__lte=snapshot_at,
    )

    totals = metric_window.aggregate(
        attempted=Coalesce(Sum("attempted_count"), Value(0)),
        delivered=Coalesce(Sum("delivered_count"), Value(0)),
        failed=Coalesce(Sum("failed_count"), Value(0)),
        delivery_runs=Count("id"),
    )

    hourly = [
        {
            "hour": row["hour"].isoformat(),
            "attempted": row["attempted"],
            "delivered": row["delivered"],
            "failed": row["failed"],
        }
        for row in (
            metric_window.annotate(hour=TruncHour("started_at"))
            .values("hour")
            .annotate(
                attempted=Coalesce(Sum("attempted_count"), Value(0)),
                delivered=Coalesce(Sum("delivered_count"), Value(0)),
                failed=Coalesce(Sum("failed_count"), Value(0)),
            )
            .order_by("hour")
        )
    ]

    daily_start = snapshot_at - timedelta(days=13)
    daily = [
        {
            "date": row["date"].isoformat(),
            "attempted": row["attempted"],
            "delivered": row["delivered"],
            "failed": row["failed"],
        }
        for row in (
            EmailDeliveryMetric.objects.filter(
                started_at__gte=daily_start,
                started_at__lte=snapshot_at,
            )
            .annotate(date=TruncDate("started_at"))
            .values("date")
            .annotate(
                attempted=Coalesce(Sum("attempted_count"), Value(0)),
                delivered=Coalesce(Sum("delivered_count"), Value(0)),
                failed=Coalesce(Sum("failed_count"), Value(0)),
            )
            .order_by("date")
        )
    ]

    # ``AnnouncementDelivery`` stores only aggregate recipient outcomes. It
    # has no immutable send-time role/audience snapshot. Attribute a run only
    # when the announcement's *current* audience is unambiguous: exactly one
    # audience row containing one supported role and no group. Public/global,
    # group, multi-row, role+group, and unsupported-role audiences remain
    # explicitly unattributed instead of being guessed.
    audience_rows_by_announcement: dict[int, list[dict]] = {}
    for row in AnnouncementAudience.objects.filter(
        announcement_id__in=announcement_window.values("announcement_id")
    ).values("announcement_id", "role_id", "role__role_name", "group_id"):
        audience_rows_by_announcement.setdefault(row["announcement_id"], []).append(
            row
        )

    role_totals = {
        role_label: {
            "attempted": 0,
            "delivered": 0,
            "failed": 0,
            "tracked_deliveries": 0,
        }
        for role_label in role_labels.values()
    }
    tracked_delivery_runs = 0
    unattributed_delivery_runs = 0
    tracked_attempted = 0
    unattributed_attempted = 0
    tracked_delivered = 0
    unattributed_delivered = 0
    tracked_failed = 0
    unattributed_failed = 0

    for delivery in announcement_window.values(
        "announcement_id",
        "announcement__visibility_scope",
        "recipient_count",
        "success_count",
        "failure_count",
    ):
        audiences = audience_rows_by_announcement.get(
            delivery["announcement_id"], []
        )
        role_label = None
        if (
            delivery["announcement__visibility_scope"]
            not in {
                Announcement.VisibilityScope.PUBLIC,
                Announcement.VisibilityScope.GLOBAL,
            }
            and len(audiences) == 1
        ):
            audience = audiences[0]
            raw_role = (audience["role__role_name"] or "").strip().lower()
            if (
                audience["role_id"] is not None
                and audience["group_id"] is None
                and raw_role in role_labels
            ):
                role_label = role_labels[raw_role]

        if role_label is None:
            unattributed_delivery_runs += 1
            unattributed_attempted += delivery["recipient_count"]
            unattributed_delivered += delivery["success_count"]
            unattributed_failed += delivery["failure_count"]
            continue

        stats = role_totals[role_label]
        stats["attempted"] += delivery["recipient_count"]
        stats["delivered"] += delivery["success_count"]
        stats["failed"] += delivery["failure_count"]
        stats["tracked_deliveries"] += 1
        tracked_delivery_runs += 1
        tracked_attempted += delivery["recipient_count"]
        tracked_delivered += delivery["success_count"]
        tracked_failed += delivery["failure_count"]

    status_by_role = [
        {
            "role": role_label,
            **stats,
            # Open/provider events are not persisted by the current schema.
            "opened": None,
        }
        for role_label, stats in role_totals.items()
    ]
    attribution = role_attribution(
        tracked_delivery_runs=tracked_delivery_runs,
        unattributed_delivery_runs=unattributed_delivery_runs,
        tracked_attempted=tracked_attempted,
        unattributed_attempted=unattributed_attempted,
        tracked_delivered=tracked_delivered,
        unattributed_delivered=unattributed_delivered,
        tracked_failed=tracked_failed,
        unattributed_failed=unattributed_failed,
    )

    recent_deliveries = [
        {
            "id": row.id,
            "announcement_id": row.announcement_id,
            "title": row.announcement.title,
            "started_at": row.started_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "status": row.status,
            "recipient_count": row.recipient_count,
            "success_count": row.success_count,
            "failure_count": row.failure_count,
            "initiated_by_name": (
                f"{row.initiated_by.first_name} {row.initiated_by.last_name}".strip()
                if row.initiated_by
                else "System"
            ),
            "initiated_by_email": row.initiated_by.email if row.initiated_by else "",
        }
        for row in (
            AnnouncementDelivery.objects.select_related("announcement", "initiated_by")
            .order_by("-started_at")[:100]
        )
    ]

    mailboxes = []
    for mailbox in (primary_mailbox, secondary_mailbox):
        mailbox_window = metric_window.filter(source_mailbox__iexact=mailbox)
        mailbox_totals = mailbox_window.aggregate(
            attempted=Coalesce(Sum("attempted_count"), Value(0)),
            delivered=Coalesce(Sum("delivered_count"), Value(0)),
            failed=Coalesce(Sum("failed_count"), Value(0)),
            delivery_runs=Count("id"),
        )
        mailbox_hourly = [
            {
                "hour": row["hour"].isoformat(),
                "attempted": row["attempted"],
                "delivered": row["delivered"],
                "failed": row["failed"],
            }
            for row in (
                mailbox_window.annotate(hour=TruncHour("started_at"))
                .values("hour")
                .annotate(
                    attempted=Coalesce(Sum("attempted_count"), Value(0)),
                    delivered=Coalesce(Sum("delivered_count"), Value(0)),
                    failed=Coalesce(Sum("failed_count"), Value(0)),
                )
                .order_by("hour")
            )
        ]
        mailbox_daily_source = EmailDeliveryMetric.objects.filter(
            source_mailbox__iexact=mailbox,
            started_at__gte=daily_start,
            started_at__lte=snapshot_at,
        )
        mailbox_daily = [
            {
                "date": row["date"].isoformat(),
                "attempted": row["attempted"],
                "delivered": row["delivered"],
                "failed": row["failed"],
            }
            for row in (
                mailbox_daily_source
                .annotate(date=TruncDate("started_at"))
                .values("date")
                .annotate(
                    attempted=Coalesce(Sum("attempted_count"), Value(0)),
                    delivered=Coalesce(Sum("delivered_count"), Value(0)),
                    failed=Coalesce(Sum("failed_count"), Value(0)),
                )
                .order_by("date")
            )
        ]
        mailboxes.append(
            {
                "email": mailbox,
                "quota_limit": quota_limit,
                "totals": mailbox_totals,
                "hourly": mailbox_hourly,
                "daily": mailbox_daily,
            }
        )

    return {
        "snapshot_at": snapshot_at.isoformat(),
        "mailboxes": mailboxes,
        # Legacy combined/single-mailbox fields retained for compatibility.
        "mailbox": primary_mailbox,
        "quota_limit": quota_limit,
        "totals": totals,
        "hourly": hourly,
        "daily": daily,
        "status_by_role": status_by_role,
        "role_attribution": attribution,
        "recent_deliveries": recent_deliveries,
        "recent_sends": _recent_email_sends(),
    }
