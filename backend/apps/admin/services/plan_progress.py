"""Current-cohort plan matrix, counted from active audience memberships (GP5)."""

from django.db.models import Count, Exists, OuterRef

from apps.groups.models.groups import group_name_sort_key
from apps.plans.models import PlanTask, PlanTaskCompletion
from apps.plans.visibility import active_audience_memberships, current_plan_groups
from apps.submissions.services import current_cohort


def get_plan_progress():
    """Read the cohort once; query count never grows with the matrix dimensions.

    Saved personal ticks count only while their owner has an active membership
    in that group with the task's audience role. Account login status is not a
    roster filter. Shared ticks count independently of audience size.
    """
    year = current_cohort()
    eligible_groups = current_plan_groups(year)
    groups = list(
        eligible_groups.annotate(group_name_key=group_name_sort_key())
        .order_by("group_name_key", "id").values("id", "group_name")
    )
    active_tasks = PlanTask.objects.active()
    tasks = list(active_tasks.select_related("stage").in_plan_order())
    stages = list({task.stage_id: task.stage for task in tasks}.values())
    sizes, completed = {}, {}

    if groups and tasks:
        memberships = active_audience_memberships(eligible_groups.values("id"))
        sizes = {
            (row["group_id"], row["membership_role"]): row["total"]
            for row in memberships.order_by().values("group_id", "membership_role")
            .annotate(total=Count("pk"))
        }
        records = PlanTaskCompletion.objects.filter(
            group__in=eligible_groups, task__in=active_tasks, completed=True,
        )
        # EXISTS avoids multiplying counts by historical membership rows.
        matching_member = memberships.filter(
            group_id=OuterRef("group_id"), user_id=OuterRef("user_id"),
            membership_role=OuterRef("task__audience_role"),
        )
        personal_counts = (
            records.filter(task__completion_mode=PlanTask.CompletionMode.PER_PERSON, user__isnull=False)
            .filter(Exists(matching_member)).order_by().values("group_id", "task_id")
            .annotate(completed=Count("pk"))
        )
        completed.update({(row["group_id"], row["task_id"]): row["completed"] for row in personal_counts})
        shared = records.filter(
            task__completion_mode=PlanTask.CompletionMode.PER_GROUP, user__isnull=True,
        ).order_by().values("group_id", "task_id")
        completed.update({(row["group_id"], row["task_id"]): 1 for row in shared})

    return {"msg": "Plan progress retrieved successfully", "data": {
        "year": year,
        "stages": [
            {"id": stage.pk, "name": stage.name, "description": stage.description, "position": stage.position}
            for stage in stages
        ],
        "tasks": [{
            "id": task.pk, "stage_id": task.stage_id, "position": task.position,
            "name": task.name, "audience_role": task.audience_role,
            "completion_mode": task.completion_mode,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        } for task in tasks],
        "groups": [{
            "id": group["id"], "name": group["group_name"],
            "cells": {str(task.pk): {
                "completed": completed.get((group["id"], task.pk), 0),
                "total": (
                    1 if task.completion_mode == PlanTask.CompletionMode.PER_GROUP
                    else sizes.get((group["id"], task.audience_role), 0)
                ),
            } for task in tasks},
        } for group in groups],
    }}
