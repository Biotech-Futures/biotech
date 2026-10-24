"""Member-facing plan shapes (GP3): stages and tasks as the group page sees them."""

from rest_framework import serializers

from .models import PlanStage, PlanTask
from .permissions import PER_PERSON, can_tick_plan_task


class PlanStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanStage
        fields = ["id", "name", "description", "position"]
        read_only_fields = fields


class GroupPlanTaskSerializer(serializers.ModelSerializer):
    """One plan task as one viewer sees it in one group.

    Context: ``facts`` (``ViewerFacts``) and ``user_id`` (the viewer). Each
    task must carry ``viewer_completions``: this group's completion records
    for the task that are either the shared record or the viewer's own, as
    prefetched by the view, so no field here makes a query.
    """

    stage_id = serializers.IntegerField(read_only=True)
    completed = serializers.SerializerMethodField()
    can_toggle = serializers.SerializerMethodField()

    class Meta:
        model = PlanTask
        fields = [
            "id",
            "stage_id",
            "position",
            "name",
            "description",
            "resource_url",
            "resource_label",
            "due_date",
            "audience_role",
            "completion_mode",
            "completed",
            "can_toggle",
        ]
        read_only_fields = fields

    def get_completed(self, task):
        """The viewer's own tick for an individual task, the group's tick for a
        shared one; False when there is no record yet.

        None for an individual task outside the viewer's audience (e.g. an
        admin looking at a student task): it is not theirs to tick, and an
        empty box would suggest it was.
        """
        facts = self.context["facts"]
        if task.completion_mode == PER_PERSON:
            if not facts.membership_role or facts.membership_role != task.audience_role:
                return None
            owner_id = self.context["user_id"]
        else:
            owner_id = None
        record = next((c for c in task.viewer_completions if c.user_id == owner_id), None)
        return bool(record and record.completed)

    def get_can_toggle(self, task):
        return can_tick_plan_task(task, self.context["facts"])
