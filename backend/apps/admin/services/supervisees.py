"""An admin changing which students a supervisor supervises, from the
supervisor's panel: by student, or by group (every student in it). A student
taken off is left with no supervisor.

A supervisor's group memberships follow their students
(apps.groups.services.sync_supervisor_memberships), so every supervisor a
student moves from or to is synced. Asked with ``preview``, nothing changes:
the answer lists who would move, for the panel's warning before it saves.
"""
from typing import Any, Dict, List, Optional

from django.db import transaction

from apps.audit.services import log_audit_event
from apps.groups.models import GroupMembership, Groups
from apps.groups.services import sync_supervisor_memberships
from apps.users.models import StudentProfile, StudentSupervisor, SupervisorProfile

STUDENT = GroupMembership.MembershipRoleChoices.STUDENT
LISTS = ("addStudentIds", "removeStudentIds", "addGroupIds", "removeGroupIds")


def _person(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.email


def _ids(raw) -> Optional[List[int]]:
    """A list of ids as given, or None when it isn't one."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        return None
    try:
        return [int(value) for value in raw]
    except (TypeError, ValueError):
        return None


def _students_in(group_ids) -> Dict[int, int]:
    """Each student in these groups now, by user id: their group's id."""
    if not group_ids:
        return {}
    return dict(
        GroupMembership.objects.filter(
            group_id__in=group_ids, left_at__isnull=True, membership_role=STUDENT,
        ).values_list("user_id", "group_id")
    )


def _supervised_by(supervisor_id: int) -> List[int]:
    return sorted(StudentProfile.objects.filter(supervisor_id=supervisor_id).values_list("user_id", flat=True))


def change_supervisees(supervisor_id: int, input_data: Dict[str, Any], initiated_by=None) -> Dict[str, Any]:
    """Add students to, or take them off, a supervisor: ``addStudentIds`` and
    ``removeStudentIds``, or every student in ``addGroupIds`` and
    ``removeGroupIds``. A student both added and taken off is added. Answers
    with each change ({studentId, name, group, from, to}, ``to`` None for a
    student left without a supervisor) and, unless ``preview``, the
    supervisor's payload after it."""
    supervisor = SupervisorProfile.objects.select_related("user").filter(user_id=supervisor_id).first()
    if supervisor is None:
        return {"msg": "Supervisor not found", "data": None}
    given = {}
    for key in LISTS:
        ids = _ids(input_data.get(key))
        if ids is None:
            return {"msg": f"{key} must be a list of ids", "data": None}
        given[key] = ids

    group_ids = set(given["addGroupIds"]) | set(given["removeGroupIds"])
    found_groups = set(Groups.objects.filter(id__in=group_ids, deleted_at__isnull=True).values_list("id", flat=True))
    if group_ids - found_groups:
        return {"msg": "Group not found", "data": None}

    added = set(given["addStudentIds"]) | set(_students_in(given["addGroupIds"]))
    removed = (set(given["removeStudentIds"]) | set(_students_in(given["removeGroupIds"]))) - added
    profiles = {
        profile.user_id: profile
        for profile in StudentProfile.objects.filter(user_id__in=added | removed).select_related(
            "user", "supervisor__user",
        )
    }
    if (set(given["addStudentIds"]) | set(given["removeStudentIds"])) - set(profiles):
        return {"msg": "Student not found", "data": None}

    # Each student's group now, to say where they are in the warning.
    group_of = dict(
        GroupMembership.objects.filter(
            user_id__in=profiles, left_at__isnull=True, membership_role=STUDENT, group__deleted_at__isnull=True,
        ).values_list("user_id", "group__group_name")
    )
    supervisor_name = _person(supervisor.user)
    changes = []
    for user_id, profile in profiles.items():
        if user_id in added and profile.supervisor_id != supervisor_id:
            was = _person(profile.supervisor.user) if profile.supervisor_id else None
            changes.append({"studentId": user_id, "to": supervisor_name, "from": was})
        elif user_id in removed and profile.supervisor_id == supervisor_id:
            changes.append({"studentId": user_id, "to": None, "from": supervisor_name})
        else:
            continue
        changes[-1].update({"name": _person(profile.user), "group": group_of.get(user_id)})
    changes.sort(key=lambda change: (change["group"] or "", change["name"].lower()))

    if input_data.get("preview") or not changes:
        data = {"changes": changes}
        if not input_data.get("preview"):
            from apps.admin.services.user import fetch_user_by_id

            data["user"] = fetch_user_by_id(supervisor_id)
        return {"msg": "ok", "data": data}

    with transaction.atomic():
        before = _supervised_by(supervisor_id)
        affected = {supervisor_id}
        for change in changes:
            profile = profiles[change["studentId"]]
            if profile.supervisor_id:
                affected.add(profile.supervisor_id)
            if change["to"] is None:
                profile.supervisor_id = None
            else:
                profile.supervisor_id = supervisor_id
                StudentSupervisor.objects.get_or_create(
                    student_user_id=profile.user_id, supervisor_user_id=supervisor_id,
                )
            profile.save(update_fields=["supervisor"])
        # Their groups follow their students, theirs and those they left.
        for affected_id in affected:
            sync_supervisor_memberships(affected_id)
        log_audit_event(
            actor=initiated_by,
            entity_type="user",
            entity_id=supervisor_id,
            action="supervisees_update",
            before_state={"supervisees": before},
            after_state={"supervisees": _supervised_by(supervisor_id)},
        )

    from apps.admin.services.user import fetch_user_by_id

    return {"msg": "ok", "data": {"changes": changes, "user": fetch_user_by_id(supervisor_id)}}
