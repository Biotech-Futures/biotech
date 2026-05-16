from django.db.models import Max
from django.utils import timezone

from apps.groups.models import GroupMembership, Groups

from .models import Task


def calculate_completion_rate(completed_tasks: int, total_tasks: int) -> int:
    if total_tasks == 0:
        return 0
    return int((completed_tasks / total_tasks) * 100)


def get_current_week_label(group_created_at) -> str:
    today = timezone.now().date()
    created = group_created_at.date() if hasattr(group_created_at, "date") else group_created_at
    week_number = (today - created).days // 7 + 1
    return f"Week {week_number}"


def get_allowed_group_ids(user):
    is_mentor = hasattr(user, "mentorprofile")
    if is_mentor:
        # Progress scope follows active mentor memberships only.
        return GroupMembership.objects.filter(
            user=user,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        ).values_list("group_id", flat=True)
    return Groups.objects.filter(
        track=user.track,
        deleted_at__isnull=True,
    ).values_list("id", flat=True)


def build_progress_snapshot(group_id=None, allowed_group_ids=None):
    task_qs = Task.objects.get_dashboard_tasks()

    if group_id is not None:
        # Deleted groups report an empty dashboard snapshot instead of leaking tasks.
        if not Groups.objects.filter(pk=group_id, deleted_at__isnull=True).exists():
            return {
                "completionRate": 0,
                "completedTasks": 0,
                "totalTasks": 0,
                "currentWeek": None,
                "nextTask": None,
                "nextTaskDate": None,
            }
        task_qs = task_qs.filter(group_id=group_id)
    elif allowed_group_ids is not None:
        task_qs = task_qs.filter(group_id__in=allowed_group_ids)

    totals = task_qs.get_task_totals()
    total_tasks = totals["total_tasks"] or 0
    completed_tasks = totals["completed_tasks"] or 0

    completion_rate = calculate_completion_rate(completed_tasks, total_tasks)

    current_week = None
    next_task_name = None
    next_task_date = None

    if group_id is not None:
        group = Groups.objects.filter(pk=group_id).first()
        if group:
            current_week = get_current_week_label(group.created_at)

        next_top_level = (
            Task.objects.active()
            .filter(group_id=group_id, parent__isnull=True, completed=False)
            .order_by("due_date")
            .first()
        )

        if next_top_level:
            next_task_name = next_top_level.name
            next_task_date = (
                Task.objects.active()
                .filter(parent_id=next_top_level.id)
                .aggregate(max_due=Max("due_date"))["max_due"]
                or next_top_level.due_date
            )

    return {
        "completionRate": completion_rate,
        "completedTasks": completed_tasks,
        "totalTasks": total_tasks,
        "currentWeek": current_week,
        "nextTask": next_task_name,
        "nextTaskDate": next_task_date,
    }
