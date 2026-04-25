from django.utils import timezone
from apps.groups.models import GroupMembership, Groups


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
        return GroupMembership.objects.filter(
            user=user,
            membership_role=GroupMembership.MembershipRole.MENTOR,
            left_at__isnull=True,
        ).values_list("group_id", flat=True)
    return Groups.objects.filter(track=user.track).values_list("id", flat=True)


def build_progress_snapshot(group_id=None):
    from django.db.models import Max, Min
    from .models import Tasks, Milestone
    from apps.groups.models import Groups

    task_qs = Tasks.objects.filter(deleted_flag=False)
    if group_id is not None:
        task_qs = task_qs.filter(milestone__group_id=group_id)

    totals = task_qs.get_task_totals()
    total_tasks = totals["total_tasks"] or 0
    completed_tasks = totals["completed_tasks"] or 0

    completion_rate = calculate_completion_rate(completed_tasks, total_tasks)

    current_week = None
    next_milestone_name = None
    next_milestone_date = None

    if group_id is not None:
        group = Groups.objects.filter(pk=group_id).first()
        if group:
            current_week = get_current_week_label(group.created_at)

        next_milestone = (
            Milestone.objects
            .filter(group_id=group_id, completed=False, deleted_flag=False)
            .annotate(earliest_task_due=Min("tasks__due_date"))
            .order_by("earliest_task_due")
            .first()
        )

        if next_milestone:
            next_milestone_name = next_milestone.milestone_name
            next_milestone_date = (
                Tasks.objects
                .filter(milestone=next_milestone, deleted_flag=False)
                .aggregate(max_due=Max("due_date"))["max_due"]
            )

    return {
        "completionRate": completion_rate,
        "completedTasks": completed_tasks,
        "totalTasks": total_tasks,
        "currentWeek": current_week,
        "nextMilestone": next_milestone_name,
        "nextMilestoneDate": next_milestone_date,
    }
