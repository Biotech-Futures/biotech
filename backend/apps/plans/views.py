"""Member endpoints for group plans (GP3)."""

from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import Groups
from apps.submissions.services import current_cohort

from .models import PlanTaskCompletion
from .permissions import can_view_group_plan, viewer_facts, visible_plan_tasks
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
