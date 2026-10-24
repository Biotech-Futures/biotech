"""Who may see a group's plan, which tasks they see, and what they may tick (GP3).

The viewer facts are worked out once per decision (``viewer_facts``); every
other decision here is made from those facts. A tick works them out again
after taking the task row lock, as access can end while it waits. ``can_tick_plan_task`` makes no
queries, so the member list can return ``can_toggle`` for every item at no
extra cost.

Rules (the group-plans technical plan, plus Will's confirmed answer on
student ticks, which supersedes the plan's earlier "students never tick
shared tasks" default):

- Audiences match the viewer's active *group membership* role, never their
  platform role.
- Admins see every active task.
- Everyone else sees the tasks for their own membership role, plus every
  shared task when they hold the shared-tick right (the group's active mentor,
  or a supervisor of a student in the group).
- Individual tasks: only the viewer's own record, and only when their
  membership role is the task's audience. Nobody, admins included, ticks for
  someone else.
- Shared tasks: an admin, the group's active mentor or a linked supervisor may
  tick any shared task. A student member may also tick a *student-audience*
  shared task. That right does not widen what a student sees.

The year check (current cohort only) belongs to the views, not to this module.
"""

from dataclasses import dataclass
from typing import Optional

from django.db.models import Q

from apps.common.rbac import group_participant_qs, is_admin
from apps.groups.models import GroupMembership

# Private helpers from the ordinary task permissions, imported on purpose:
# the shared-tick right must match who may tick an ordinary group task (the
# group's active mentor, or a supervisor of a student in the group) exactly,
# and importing keeps the two in step. Their behaviour is not changed here.
from apps.tasks.permissions import _is_active_group_mentor, _supervises_any_in_group

from .models import PlanTask

STUDENT = GroupMembership.MembershipRoleChoices.STUDENT
PER_PERSON = PlanTask.CompletionMode.PER_PERSON
PER_GROUP = PlanTask.CompletionMode.PER_GROUP


@dataclass(frozen=True)
class ViewerFacts:
    """Everything the plan permissions need to know about one viewer in one group."""

    is_admin: bool
    # The viewer's active membership role in this group; None without an
    # active membership. A supervisor linked only through a student's profile
    # has None here, so they get no supervisor individual tasks.
    membership_role: Optional[str]
    # May tick any shared task: an admin, the group's active mentor, or a
    # supervisor of a student in the group (with or without a membership row).
    holds_tick_right: bool


def viewer_facts(user, group) -> ViewerFacts:
    """Work out the viewer's facts for ``group``, as they stand now."""
    if not user or not user.is_authenticated:
        return ViewerFacts(is_admin=False, membership_role=None, holds_tick_right=False)

    admin = is_admin(user)
    # At most one active membership per (group, user), by constraint.
    membership_role = (
        group_participant_qs(user, group.id)
        .values_list("membership_role", flat=True)
        .first()
    )
    holds_tick_right = (
        admin
        or _is_active_group_mentor(user, group.id)
        or _supervises_any_in_group(user, group.id)
    )
    return ViewerFacts(
        is_admin=admin,
        membership_role=membership_role,
        holds_tick_right=holds_tick_right,
    )


def can_view_group_plan(facts: ViewerFacts) -> bool:
    """An admin, an active member, or a shared-tick holder (which covers a
    supervisor linked only through a student's profile). Others get a 404."""
    return facts.is_admin or facts.membership_role is not None or facts.holds_tick_right


def visible_plan_tasks(facts: ViewerFacts):
    """Active plan tasks this viewer may see. Use for both listing and ticking,
    so a task that isn't listed can't be ticked either."""
    tasks = PlanTask.objects.active()
    if facts.is_admin:
        return tasks

    visible = Q()
    if facts.membership_role:
        visible |= Q(audience_role=facts.membership_role)
    if facts.holds_tick_right:
        visible |= Q(completion_mode=PER_GROUP)
    if not visible:
        return tasks.none()
    return tasks.filter(visible)


def can_tick_plan_task(task: PlanTask, facts: ViewerFacts) -> bool:
    """Whether this viewer may tick ``task`` in this group. Makes no queries.

    Assumes ``task`` is one ``visible_plan_tasks(facts)`` returned; callers
    answer 404 for anything else before asking this.
    """
    if task.completion_mode == PER_PERSON:
        # Only the viewer's own record, and only in the task's audience.
        return bool(facts.membership_role) and facts.membership_role == task.audience_role

    if facts.holds_tick_right:
        return True
    # Will's confirmed answer: students may tick shared tasks meant for students.
    return facts.membership_role == STUDENT and task.audience_role == STUDENT
