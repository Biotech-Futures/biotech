"""Member endpoints for group plans (GP3)."""

from django.db import transaction
from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.groups.models import Groups
from apps.submissions.services import current_cohort

from .models import PlanTask, PlanTaskCompletion
from .permissions import (
    PER_PERSON,
    can_tick_plan_task,
    can_view_group_plan,
    viewer_facts,
    visible_plan_tasks,
)
from .serializers import GroupPlanTaskSerializer, PlanStageSerializer
from .visibility import group_sees_plan


class GroupPlanTaskListView(APIView):
    """GET /api/v1/plans/groups/<group_id>/tasks/ - a group's plan for this viewer.

    404 when the group is missing or deleted, or the viewer may not see its
    plan; 200 with empty ``stages``/``items`` for a group outside the current
    cohort; otherwise the visible tasks in plan order, each with the viewer's
    ``completed`` and ``can_toggle``, and the stages those tasks belong to.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = Groups.objects.active().filter(pk=group_id).first()
        if group is None:
            raise NotFound("Group not found.")
        facts = viewer_facts(request.user, group)
        if not can_view_group_plan(facts):
            raise NotFound("Group not found.")

        year = current_cohort()  # Read once per request.
        if not group_sees_plan(group, year):
            return Response({"year": year, "stages": [], "items": []})

        # This group's shared records and the viewer's own records only, in
        # one query whatever the number of tasks.
        viewer_completions = PlanTaskCompletion.objects.filter(group=group).filter(
            Q(user__isnull=True) | Q(user=request.user)
        )
        tasks = list(
            visible_plan_tasks(facts)
            .select_related("stage")
            .in_plan_order()
            .prefetch_related(
                Prefetch("completions", queryset=viewer_completions, to_attr="viewer_completions")
            )
        )

        # Stages with at least one visible task, in plan order (tasks already are).
        stages = list({task.stage_id: task.stage for task in tasks}.values())
        context = {"facts": facts, "user_id": request.user.id}
        return Response({
            "year": year,
            "stages": PlanStageSerializer(stages, many=True).data,
            "items": GroupPlanTaskSerializer(tasks, many=True, context=context).data,
        })


def _requested_completion(data):
    """The requested value from a check body: True/False, or None to flip.

    Accepts only ``{}`` or ``{"completed": <JSON boolean>}``. Anything else,
    including a user id, is a 400: whose record changes is never the
    client's choice.
    """
    if not isinstance(data, dict):
        raise ValidationError("Expected a JSON object.")
    unknown = set(data) - {"completed"}
    if unknown:
        raise ValidationError(f"Unexpected field(s): {', '.join(sorted(unknown))}.")
    if "completed" not in data:
        return None
    value = data["completed"]
    if type(value) is not bool:  # Rejects 1/0, "true", null, etc.
        raise ValidationError("'completed' must be true or false.")
    return value


class GroupPlanTaskCheckView(APIView):
    """POST /api/v1/plans/groups/<group_id>/tasks/<task_id>/check/ - tick or untick.

    Body ``{"completed": true|false}`` sets the viewer's tick; ``{}`` flips it.
    Checks run 404 (no such group, no plan access, not a current-year group,
    or the task is not visible to this viewer), then 403 (visible but not the
    viewer's to tick), then 400 (bad body). A student asking for a mentor or
    supervisor shared task therefore gets 404, as for any task they can't see.

    Individual tasks change only the requesting user's own record; shared
    tasks change the group's single record (``user=None``). Returns the
    updated item in the list's shape.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, task_id):
        group = Groups.objects.active().filter(pk=group_id).first()
        if group is None:
            raise NotFound("Group not found.")
        facts = viewer_facts(request.user, group)
        if not can_view_group_plan(facts) or not group_sees_plan(group, current_cohort()):
            raise NotFound("Group not found.")

        with transaction.atomic():
            # Lock the task row first: the same lock task edits and soft
            # deletion take, so a tick can't race a change of audience, mode
            # or deletion, and first ticks for the same task are serialised.
            # Visibility is then read after the lock, from committed state.
            task = PlanTask.objects.select_for_update().filter(pk=task_id).first()
            if task is None or not visible_plan_tasks(facts).filter(pk=task.pk).exists():
                raise NotFound("Task not found.")
            if not can_tick_plan_task(task, facts):
                raise PermissionDenied("You can't tick this task.")
            requested = _requested_completion(request.data)

            owner = request.user if task.completion_mode == PER_PERSON else None
            record = PlanTaskCompletion.objects.filter(task=task, group=group, user=owner).first()
            before = bool(record and record.completed)
            after = (not before) if requested is None else requested

            if after != before:
                if record is None:
                    # Only reachable when ticking: an untick with no record
                    # is a no-op and creates nothing.
                    record = PlanTaskCompletion.objects.create(
                        task=task, group=group, user=owner, completed=after,
                    )
                else:
                    record.completed = after
                    record.save(update_fields=["completed", "updated_at"])
                state = {
                    "group_id": group.id,
                    "completion_mode": task.completion_mode,
                    # Whose record changed: the viewer for an individual
                    # task, None for the group's shared record.
                    "completion_user_id": getattr(owner, "id", None),
                }
                log_audit_event(
                    actor=request.user,
                    entity_type="plan_task",
                    entity_id=task.id,
                    action="toggle",
                    before_state={**state, "completed": before},
                    after_state={**state, "completed": after},
                )

        task.viewer_completions = [record] if record is not None else []
        context = {"facts": facts, "user_id": request.user.id}
        return Response(GroupPlanTaskSerializer(task, context=context).data)
