"""CSV rows for the four Vue analytics pages."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from apps.admin.services.analytics import (
    get_email_delivery_analytics,
    get_group_activity_analytics,
    get_resource_analytics,
)
from apps.chat.models import Messages
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import AdminScope, User


def _participants(*, include_admin=False):
    now = timezone.now()
    admin_ids = AdminScope.objects.values("user_id")
    users = list((User.objects.all() if include_admin else User.objects.exclude(id__in=admin_ids)).order_by("id"))
    roles = {}
    for row in (RoleAssignmentHistory.objects.filter(user_id__in=[u.id for u in users], valid_from__lte=now)
                .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
                .select_related("role").order_by("user_id", "-valid_from", "-id")):
        roles.setdefault(row.user_id, row.role.role_name.lower())
    return [(user, roles[user.id]) for user in users if roles.get(user.id) in {"student", "mentor", "supervisor"}]


def _group_snapshot():
    groups = list(Groups.objects.active().values("id", "group_name"))
    memberships = list(GroupMembership.objects.filter(
        group_id__in=[group["id"] for group in groups], left_at__isnull=True,
    ).values("group_id", "user_id", "membership_role"))
    return groups, memberships


def _percent(count, total):
    return (count * 200 + total) // (2 * total) if total else 0


def _rounded_ratio(count, total, places):
    return float((Decimal(count) / Decimal(total)).quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP,
    ))


def build_page_report(params):
    report = params["report"]
    if report == "messages":
        return _messages_report(params)
    year = params["year"]
    if report == "users":
        participants = _participants()
        by_role = {role: [user for user, name in participants if name == role]
                   for role in ("student", "mentor", "supervisor")}
        rows = [["Year", year], ["Total Users", len(participants)]]
        rows += [[role.title() + "s", len(users)] for role, users in by_role.items()]
        rows += [[role.title() + "s Logged In (%)", _percent(
            sum(user.last_login is not None and user.last_login.year == year for user in users), len(users),
        )] for role, users in by_role.items()]
        return (), rows, f"users-analytics-{year}.csv"

    if report == "groups":
        groups, memberships = _group_snapshot()
        student_counts = Counter(row["group_id"] for row in memberships if row["membership_role"] == "student")
        mentor_groups = {row["group_id"] for row in memberships if row["membership_role"] == "mentor"}
        mentors = {row["user_id"] for row in memberships if row["membership_role"] == "mentor"}
        students = {row["user_id"] for row in memberships if row["membership_role"] == "student"}
        ratio = round(len(students) / len(mentors), 2) if mentors else None
        rows = [["Groups Analytics", year], [], ["Metric", "Value"],
                ["Total Groups", len(groups)],
                ["Average Group Size", f"{_rounded_ratio(sum(student_counts.values()), len(groups), 1):g}" if groups else 0],
                ["Groups with Mentor", len(mentor_groups)],
                ["Groups without Mentor", len(groups) - len(mentor_groups)],
                ["Mentor-to-Student Ratio", f"1:{ratio:g}" if ratio is not None else "N/A"]]
        return (), rows, f"groups-analytics-{year}.csv"

    if report == "overview":
        return _overview_report(params)


def _overview_report(params):
    year = params["year"]
    participants = _participants()
    users = [user for user, _ in participants]
    roles = Counter(role for _, role in participants)
    groups, memberships = _group_snapshot()
    with_mentor = {row["group_id"] for row in memberships if row["membership_role"] == "mentor"}
    assigned = {row["user_id"] for row in memberships if row["membership_role"] == "mentor"}
    activity = get_group_activity_analytics()
    observed = [user.last_login or user.activated_at or user.invited_at for user in users]
    observed += [row["date"] for row in activity["messages_by_day"]]
    as_of = max((value.date() if hasattr(value, "date") else value for value in observed if value), default=timezone.now().date())
    logged_in = sum(user.last_login is not None for user in users)
    active = sum(user.is_active for user in users)
    deactivated = sum(not user.is_active or user.account_status in {"deactivated", "suspended"} for user in users)
    registrations = Counter(user.date_joined.date() for user, role in participants
                            if role in {"student", "mentor"} and user.date_joined)
    registration_period = params.get("registration_period", "year")
    if registration_period == "year":
        registration_value = sum(value for day, value in registrations.items() if day.year == max((d.year for d in registrations), default=year))
        registration_unit = "latest year"
        registration_helper = "Account creation dates for current participants by year."
    elif registration_period == "month":
        latest = max((day for day in registrations if day.year == year), default=date(year, 12, 31))
        registration_value = sum(value for day, value in registrations.items() if day.year == year and day.month == latest.month)
        registration_unit = "latest month"
        registration_helper = f"Monthly registrations stored for {year}."
    else:
        latest = max(registrations, default=date(year, 12, 31))
        days = 7 if registration_period == "week" else 1
        registration_value = sum(value for day, value in registrations.items() if latest - timedelta(days=days - 1) <= day <= latest)
        registration_unit = "latest week" if days == 7 else "latest day"
        registration_helper = ("New registrations over the most recent 8 database weeks." if days == 7
                               else "New registrations over the most recent 7 database days.")
    mentor_rate = _percent(len(assigned), roles["mentor"])
    source = "seed-derived"
    rows = [
        ["Total Participants", len(users), f'{roles["student"]} students · {roles["mentor"]} mentors · {roles["supervisor"]} supervisors', source],
        ["Registered Groups", len(groups), f"{len(with_mentor)} with mentor · {len(groups) - len(with_mentor)} without mentor", source],
        ["Mentor Utilisation", f"{mentor_rate}%", f'{len(assigned)} of {roles["mentor"]} mentors assigned to groups', source],
        ["Logged In", f"{_percent(logged_in, len(users))}%", f"{logged_in} of {len(users)} participants have logged in", source],
        ["New Registrations", f"{registration_value} {registration_unit}", registration_helper, source],
        ["Users", f"{len(users)} Total Users", "Current account status from the local database", source],
        ["Groups", f"{len(groups)} groups", f"{len(with_mentor)} groups currently have a mentor.", source],
        ["Mentor Coverage", f"{mentor_rate}% Utilised", f"{len(assigned)} mentors currently assigned to groups", source],
        ["Activity", f'{sum(user.last_login is not None and user.last_login.date() == as_of for user in users)} Daily Active',
         "Daily active users over the most recent 7 database days.", source],
        ["Messages", f'{sum(row["message_count"] for row in activity["messages_by_group"]):,} Messages',
         "Messages stored in the local database", source],
        ["Resources", f'{get_resource_analytics()["total_clicks"]:,} Clicks',
         "Resource access events stored in the local database", source],
        ["Email Monitoring", f'{get_email_delivery_analytics()["totals"]["attempted"]:,} 24h recipients',
         "Announcement delivery attempts in the latest rolling 24-hour database window", source],
    ]
    return ("Metric", "Value", "Notes", "Data Source"), rows, f"biotech-analytics-{year}.csv"


def _messages_report(params):
    start, end = params["start_date"], params["end_date"]
    mode = params.get("mode", "groups")
    show_all_details = params["show_all_details"]
    group_id = params.get("group_id")
    role = params.get("user_role", "all")
    search = params.get("search", "").strip()
    sort_by = params.get("sort_by", "value")
    if mode == "users" and sort_by not in {"value", "last7Days"}:
        sort_by = "value"
    sort_order = params.get("sort_order", "desc")
    activity = get_group_activity_analytics(start_date=start, end_date=end)
    groups = sorted(activity["messages_by_group"], key=lambda row: -row["message_count"])
    all_activity = get_group_activity_analytics() if show_all_details else None
    anchor = params.get("anchor_date") or end
    recent = get_group_activity_analytics(start_date=anchor - timedelta(days=6), end_date=anchor)
    recent_groups = {row["group_id"]: row["message_count"] for row in recent["messages_by_group"]}
    recent_users = {row["user_id"]: row["message_count"] for row in _message_users_for_group(recent, group_id)}
    group = next((row for row in groups if row["group_id"] == group_id), None)
    duplicate = group and sum(row["group_name"] == group["group_name"] for row in groups) > 1
    group_label = (f'{group["group_name"]} (ID {group_id})' if duplicate else group["group_name"]) if group else (f"Group {group_id}" if group_id else "All groups")
    period_label = f"{start.day} {start:%b} {start.year}–{end.day} {end:%b} {end.year} (UTC)"
    rows = [["Messages Analytics", f"{start} to {end}"], ["View", mode.title()], ["Period", period_label],
            ["Trend Interval", params["interval"]],
            ["Period Start (UTC)", start.isoformat()], ["Period End (UTC)", end.isoformat()],
            ["Group", group_label], ["Group ID", group_id or "all"],
            ["Role", role if mode == "users" else "All Roles"], ["Search", search or "None"],
            ["Sort", f"{sort_by} {sort_order}"], []]
    lifetime_messages = Messages.objects.filter(deleted_at__isnull=True, group__deleted_at__isnull=True)
    if group_id:
        lifetime_messages = lifetime_messages.filter(group_id=group_id)
    lifetime_total = lifetime_messages.count()
    if mode == "groups":
        visible = [row for row in groups if not group_id or row["group_id"] == group_id]
        period_total = sum(row["message_count"] for row in visible)
        with_messages = sum(row["message_count"] > 0 for row in visible)
        least = min(visible, key=lambda row: row["message_count"], default=None)
        detail_groups = (
            sorted(
                [row for row in all_activity["messages_by_group"] if not group_id or row["group_id"] == group_id],
                key=lambda row: -row["message_count"],
            )
            if all_activity else visible
        )
        detail_start = all_activity["messages_by_day"][0]["date"] if all_activity and all_activity["messages_by_day"] else anchor
        days = max(1, ((anchor if all_activity else end) - (detail_start if all_activity else start)).days + 1)
        detail_total = max(sum(row["message_count"] for row in detail_groups), 1)
        detail = [{"id": row["group_id"], "name": row["group_name"], "value": row["message_count"],
                   "avgPerDay": _rounded_ratio(row["message_count"], days, 2),
                   "last7Days": recent_groups.get(row["group_id"], 0),
                   "share": _rounded_ratio(row["message_count"] * 100, detail_total, 1)} for row in detail_groups]
        rows += [["Metric", "Value"], ["Messages (All Time)", lifetime_total],
                 ["Messages This Period", period_total],
                 ["Average per Group", f"{_rounded_ratio(period_total, with_messages, 1):.1f}" if with_messages else "0.0"],
                 ["Groups with Messages", with_messages],
                 ["Most Active Group", visible[0]["group_name"] if visible else "—"],
                 ["Lowest Message Group", least["group_name"] if least else "—"], [],
                 ["Group ID", "Group", "Messages", "Average per Day", "Messages in Last 7 Observed Days"]]
        detail = [row for row in detail if search.casefold() in row["name"].casefold()]
        detail.sort(key=lambda row: row[sort_by], reverse=sort_order == "desc")
        rows += [[row["id"], row["name"], row["value"], f'{row["avgPerDay"]:g}', row["last7Days"]] for row in detail]
    else:
        participants = dict((user.id, role_name.title()) for user, role_name in _participants(include_admin=True))
        group_names = dict(Groups.objects.active().order_by("-created_at", "id").values_list("id", "group_name"))
        names = defaultdict(set)
        for membership in GroupMembership.objects.filter(group_id__in=group_names, left_at__isnull=True).exclude(membership_role="").order_by("group_id", "id"):
            names[membership.user_id].add(membership.group_id)
        def user_details(source):
            return [{"id": row["user_id"], "name": row["name"],
                     "role": participants.get(row["user_id"], "Unavailable"),
                     "value": row["message_count"], "last7Days": recent_users.get(row["user_id"], 0)}
                    for row in _message_users_for_group(source, group_id)
                    if role == "all" or participants.get(row["user_id"], "Unavailable") == role]

        visible = user_details(activity)
        period_total = sum(row["message_count"] for row in groups if not group_id or row["group_id"] == group_id)
        rows += [["Metric", "Value"], ["Messages (All Time)", lifetime_total],
                 ["Messages This Period", period_total],
                 ["Users with Messages", sum(row["value"] > 0 for row in visible)],
                 ["Most Active User", visible[0]["name"] if visible else "—"], [],
                 ["User ID", "User", "Role", "Current Group(s)", "Messages", "Messages in Last 7 Observed Days"]]
        if all_activity:
            visible = user_details(all_activity)
        visible = [row for row in visible if search.casefold() in row["name"].casefold()]
        visible.sort(key=lambda row: row[sort_by], reverse=sort_order == "desc")
        rows += [[row["id"], row["name"], row["role"], ", ".join(
            group_name for group_id, group_name in group_names.items() if group_id in names[row["id"]]
        ) or "Group —",
                  row["value"], row["last7Days"]] for row in visible]
    return (), rows, f"messages-analytics-{mode}-{end}.csv"


def _message_users_for_group(activity, group_id):
    """Scope user counts using message facts, never current membership guesses."""
    users = activity["messages_by_user"]
    if group_id:
        totals = Counter()
        for row in activity["messages_by_user_by_group_by_day"]:
            if row["group_id"] == group_id:
                totals[row["user_id"]] += row["message_count"]
        users = [{**row, "message_count": totals[row["user_id"]]}
                 for row in users if row["user_id"] in totals]
    return sorted(users, key=lambda row: -row["message_count"])
