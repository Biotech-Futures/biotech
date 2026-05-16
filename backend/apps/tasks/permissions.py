from __future__ import annotations

from rest_framework import permissions

from apps.groups.models import GroupMembership, Groups
from apps.users.models import StudentProfile
from apps.users.utils.admin_scope import (
    can_admin_track,
    get_admin_track_ids,
    is_operational_admin,
)

from .models import CreatorRole, Task, TaskType


def _supervisor_user_id_for(student_user_id):
    if not student_user_id:
        return None
    return (
        StudentProfile.objects.filter(user_id=student_user_id)
        .values_list("supervisor_id", flat=True)
        .first()
    )


def _supervisee_user_ids(supervisor_user):
    if not supervisor_user or not supervisor_user.is_authenticated:
        return []
    return list(
        StudentProfile.objects.filter(supervisor_id=supervisor_user.id)
        .values_list("user_id", flat=True)
    )


def _mentor_group_ids(user):
    return list(
        GroupMembership.objects.filter(
            user=user,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        ).values_list("group_id", flat=True)
    )


def _student_group_ids(user):
    return list(
        GroupMembership.objects.filter(
            user=user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        )
        .values_list("group_id", flat=True)
    )


def _supervisor_group_ids(user, supervisee_user_ids=None):
    student_ids = (
        supervisee_user_ids
        if supervisee_user_ids is not None
        else _supervisee_user_ids(user)
    )
    if not student_ids:
        return []
    return list(
        GroupMembership.objects.filter(
            user_id__in=student_ids,
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        )
        .values_list("group_id", flat=True)
        .distinct()
    )


def _is_active_group_mentor(user, group_id):
    if not group_id:
        return False
    return GroupMembership.objects.filter(
        group_id=group_id,
        user=user,
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        left_at__isnull=True,
        group__deleted_at__isnull=True,
    ).exists()


def _is_supervisor_of(user, student_user_id):
    if not student_user_id:
        return False
    return _supervisor_user_id_for(student_user_id) == user.id


def _supervises_any_in_group(user, group_id):
    if not group_id:
        return False
    student_ids = _supervisee_user_ids(user)
    if not student_ids:
        return False
    return GroupMembership.objects.filter(
        group_id=group_id,
        user_id__in=student_ids,
        left_at__isnull=True,
        group__deleted_at__isnull=True,
    ).exists()


def _user_active_group_id(user_id):
    # Intended to find the group an assignee belongs to. Excludes the
    # auto-created SUPERVISOR rows so a supervisor's supervisee group isn't
    # mistaken for the supervisor's "own" group, while still allowing mentor
    # and student memberships through (so non-student assignees still resolve
    # to a meaningful group/track).
    return (
        GroupMembership.objects.filter(
            user_id=user_id,
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        )
        .exclude(membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR)
        .values_list("group_id", flat=True)
        .first()
    )


def _user_is_student(user_id):
    if not user_id:
        return False
    return StudentProfile.objects.filter(user_id=user_id).exists()


def _resolve_track_id(task_type, group, assigned_user):
    if task_type == TaskType.GROUP and group is not None:
        gid = group.id if hasattr(group, "id") else group
        return Groups.objects.filter(
            pk=gid,
            deleted_at__isnull=True,
        ).values_list("track_id", flat=True).first()
    if task_type == TaskType.INDIVIDUAL and assigned_user is not None:
        uid = assigned_user.id if hasattr(assigned_user, "id") else assigned_user
        group_id = _user_active_group_id(uid)
        if group_id:
            return Groups.objects.filter(pk=group_id).values_list("track_id", flat=True).first()
    return None


def _task_track_id(task):
    if task.task_type == TaskType.GROUP and task.group_id:
        return Groups.objects.filter(
            pk=task.group_id,
            deleted_at__isnull=True,
        ).values_list("track_id", flat=True).first()
    if task.task_type == TaskType.INDIVIDUAL and task.assigned_user_id:
        group_id = _user_active_group_id(task.assigned_user_id)
        if group_id:
            return Groups.objects.filter(pk=group_id).values_list("track_id", flat=True).first()
    return None


def resolve_creator_role(user, task_type, group=None, assigned_user=None):
    if is_operational_admin(user):
        track_ids = get_admin_track_ids(user)
        if track_ids is None:
            return CreatorRole.GLOBAL_ADMIN
        target_track_id = _resolve_track_id(task_type, group, assigned_user)
        if target_track_id is not None and target_track_id in track_ids:
            return CreatorRole.TRACK_ADMIN

    if task_type == TaskType.GROUP and group is not None:
        gid = group.id if hasattr(group, "id") else group
        if _is_active_group_mentor(user, gid):
            return CreatorRole.MENTOR
        if _supervises_any_in_group(user, gid):
            return CreatorRole.SUPERVISOR

    if task_type == TaskType.INDIVIDUAL and assigned_user is not None:
        assignee_id = assigned_user.id if hasattr(assigned_user, "id") else assigned_user
        assignee_group_id = _user_active_group_id(assignee_id)
        if assignee_group_id and _is_active_group_mentor(user, assignee_group_id):
            return CreatorRole.MENTOR
        if _is_supervisor_of(user, assignee_id):
            return CreatorRole.SUPERVISOR

    return CreatorRole.STUDENT


def visible_tasks(user, *, include_deleted=False):
    from django.db.models import Q

    base = Task.objects.all() if include_deleted else Task.objects.active()
    # Deleted groups do not grant task visibility, including recovery views.
    base = base.filter(Q(group__isnull=True) | Q(group__deleted_at__isnull=True))

    if not user or not user.is_authenticated:
        return base.none()

    track_ids = get_admin_track_ids(user) if is_operational_admin(user) else []
    if is_operational_admin(user) and track_ids is None:
        return base

    mentor_group_ids = _mentor_group_ids(user)
    supervisee_user_ids = _supervisee_user_ids(user)
    supervisor_group_ids = _supervisor_group_ids(user, supervisee_user_ids)
    student_group_ids = _student_group_ids(user)

    visibility = Q(pk__in=[])

    if track_ids:
        admin_group_ids = list(
            Groups.objects.filter(
                track_id__in=track_ids,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )
        user_ids_in_admin_tracks = list(
            GroupMembership.objects.filter(
                group_id__in=admin_group_ids,
                left_at__isnull=True,
                group__deleted_at__isnull=True,
            ).values_list("user_id", flat=True)
        )
        visibility |= Q(task_type=TaskType.GROUP, group_id__in=admin_group_ids)
        visibility |= Q(
            task_type=TaskType.INDIVIDUAL,
            assigned_user_id__in=user_ids_in_admin_tracks,
        )

    if mentor_group_ids:
        student_ids_in_mentor_groups = list(
            GroupMembership.objects.filter(
                group_id__in=mentor_group_ids,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                group__deleted_at__isnull=True,
            ).values_list("user_id", flat=True)
        )
        visibility |= Q(task_type=TaskType.GROUP, group_id__in=mentor_group_ids)
        visibility |= Q(
            task_type=TaskType.INDIVIDUAL,
            assigned_user_id__in=student_ids_in_mentor_groups,
        )

    if supervisor_group_ids:
        visibility |= Q(task_type=TaskType.GROUP, group_id__in=supervisor_group_ids)
    if supervisee_user_ids:
        visibility |= Q(
            task_type=TaskType.INDIVIDUAL,
            assigned_user_id__in=supervisee_user_ids,
        )

    if student_group_ids:
        visibility |= Q(task_type=TaskType.GROUP, group_id__in=student_group_ids)

    visibility |= Q(task_type=TaskType.INDIVIDUAL, assigned_user=user)

    return base.filter(visibility).distinct()


def _can_create_task(user, payload):
    task_type = payload.get("task_type")
    group_id = payload.get("group")
    assigned_user_id = payload.get("assigned_user")

    if task_type == TaskType.GROUP and not group_id:
        return False
    if task_type == TaskType.INDIVIDUAL and not assigned_user_id:
        return False

    target_track_id = None
    if task_type == TaskType.GROUP:
        target_track_id = (
            Groups.objects.filter(
                pk=group_id,
                deleted_at__isnull=True,
            ).values_list("track_id", flat=True).first()
        )
    elif task_type == TaskType.INDIVIDUAL:
        assignee_group_id = _user_active_group_id(assigned_user_id)
        if assignee_group_id:
            target_track_id = (
                Groups.objects.filter(pk=assignee_group_id)
                .filter(deleted_at__isnull=True)
                .values_list("track_id", flat=True)
                .first()
            )

    if target_track_id is not None and can_admin_track(user, target_track_id):
        return True

    if task_type == TaskType.GROUP:
        return _is_active_group_mentor(user, group_id) or _supervises_any_in_group(
            user, group_id
        )

    # Student self-creation: assignee == self is the only allowed Student path.
    if assigned_user_id == user.id:
        return True

    assignee_group_id = _user_active_group_id(assigned_user_id)
    if assignee_group_id and _is_active_group_mentor(user, assignee_group_id):
        return True
    return _is_supervisor_of(user, assigned_user_id)


def _can_modify_task(user, task: Task) -> bool:
    track_id = _task_track_id(task)
    if track_id is not None and can_admin_track(user, track_id):
        return True
    if task.created_by_id == user.id:
        return True

    # Mentor of the group can edit any group task; supervisor of any active
    # group student can edit any group task in that group.
    if task.task_type == TaskType.GROUP:
        if _is_active_group_mentor(user, task.group_id):
            return True
        if _supervises_any_in_group(user, task.group_id):
            return True

    # Student-created tasks: mentor / supervisor reach extends to CRUD.
    if task.creator_role == CreatorRole.STUDENT:
        if task.task_type == TaskType.INDIVIDUAL:
            assignee_group_id = _user_active_group_id(task.assigned_user_id)
            if assignee_group_id and _is_active_group_mentor(user, assignee_group_id):
                return True
            if _is_supervisor_of(user, task.assigned_user_id):
                return True
    return False


class IsTaskManager(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method == "POST":
            return _can_create_task(user, request.data)
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return _can_modify_task(request.user, obj)


def _can_toggle(user, task: Task) -> bool:
    track_id = _task_track_id(task)
    if track_id is not None and can_admin_track(user, track_id):
        return True

    if task.task_type == TaskType.GROUP:
        if _is_active_group_mentor(user, task.group_id):
            return True
        if _supervises_any_in_group(user, task.group_id):
            return True
        return False

    # Individual task. Two cases per spec §5.2.
    if task.assigned_user_id == user.id:
        return True

    assignee_is_student = _user_is_student(task.assigned_user_id)
    if not assignee_is_student:
        # Case 2: only the assignee + Admin (handled above) may toggle.
        return False

    # Case 1: Student-assignee — role-class restricted.
    if task.creator_role in (CreatorRole.GLOBAL_ADMIN, CreatorRole.TRACK_ADMIN):
        return _is_active_group_mentor(
            user, _user_active_group_id(task.assigned_user_id)
        ) or _is_supervisor_of(user, task.assigned_user_id)
    if task.creator_role == CreatorRole.MENTOR:
        return _is_active_group_mentor(
            user, _user_active_group_id(task.assigned_user_id)
        )
    if task.creator_role == CreatorRole.SUPERVISOR:
        return _is_supervisor_of(user, task.assigned_user_id)
    if task.creator_role == CreatorRole.STUDENT:
        # Student-created task: peers (Mentor of group / Supervisor of student) can toggle.
        return _is_active_group_mentor(
            user, _user_active_group_id(task.assigned_user_id)
        ) or _is_supervisor_of(user, task.assigned_user_id)
    return False


class CanToggleTask(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return _can_toggle(request.user, obj)
