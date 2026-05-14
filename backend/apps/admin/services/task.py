from typing import TypedDict, Optional, List, Dict, Any

from django.db import transaction
from django.db.models import Q

from apps.tasks.models import Task, TaskStatus, TaskType, CreatorRole
from apps.tasks.permissions import resolve_creator_role
from apps.groups.models import Groups, GroupMembership
from apps.admin.scope_utils import get_admin_track_ids


def _admin_visible_tasks(requesting_user):
    """
    Tasks visible to an admin based on AdminScope; Django staff/superuser
    flags do not widen track-scoped task visibility.
    """
    base = Task.objects.active()

    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is None:
        # Global Admin: sees everything
        return base

    if not track_ids:
        return base.none()

    # Track Admin: only tasks belonging to groups in their tracks,
    # or individual tasks assigned to users in those groups
    admin_group_ids = list(
        Groups.objects.filter(track_id__in=track_ids).values_list("id", flat=True)
    )
    user_ids_in_tracks = list(
        GroupMembership.objects
        .filter(group_id__in=admin_group_ids, left_at__isnull=True)
        .values_list("user_id", flat=True)
    )
    visibility = (
        Q(task_type=TaskType.GROUP, group_id__in=admin_group_ids)
        | Q(task_type=TaskType.INDIVIDUAL, assigned_user_id__in=user_ids_in_tracks)
        | Q(task_type=TaskType.INDIVIDUAL, assigned_user__track_id__in=track_ids)
        | Q(task_type=TaskType.INDIVIDUAL, assigned_user=requesting_user)
    )
    return base.filter(visibility).distinct()


# Type definitions
class TaskDict(TypedDict):
    id: int
    name: str
    description: str
    due_date: Optional[str]
    status: str
    completed: bool
    parent: Optional[int]
    task_type: str
    group: Optional[int]
    assigned_user: Optional[int]
    created_by: Optional[Dict[str, Any]]
    creator_role: str
    deleted_at: Optional[str]
    created_at: str
    updated_at: str


class TaskResponseDict(TypedDict):
    msg: str
    data: Optional[Any]


# ─── helpers ────────────────────────────────────────────────────────────────

def _serialize_task(task: Task) -> TaskDict:
    """Serialize a Task model instance to a dictionary."""
    created_by = None
    if task.created_by_id and task.created_by:
        user = task.created_by
        name = f"{user.first_name} {user.last_name}".strip() or None
        created_by = {"id": user.id, "name": name}

    return {
        "id": task.id,
        "name": task.name,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "status": task.status,
        "completed": task.completed,
        "parent": task.parent_id,
        "task_type": task.task_type,
        "group": task.group_id,
        "assigned_user": task.assigned_user_id,
        "created_by": created_by,
        "creator_role": task.creator_role,
        "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


# ─── queries ─────────────────────────────────────────────────────────────────

def list_admin_tasks(
    requesting_user,
    page: int = 1,
    limit: int = 10,
    task_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List tasks visible to the requesting admin with optional type filter.

    Args:
        requesting_user: The authenticated admin user
        page: Page number (1-indexed)
        limit: Items per page
        task_type: Optional filter — "group" or "individual"

    Returns:
        Dictionary with tasks list and pagination info
    """
    qs = _admin_visible_tasks(requesting_user).select_related("created_by")
    if task_type:
        qs = qs.filter(task_type=task_type)

    offset = (page - 1) * limit
    total = qs.count()
    items = [_serialize_task(t) for t in qs[offset:offset + limit]]
    has_more = offset + len(items) < total

    return {
        "msg": "Tasks retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


def get_admin_task_by_id(requesting_user, task_id: int) -> TaskResponseDict:
    """
    Get a single task by ID if visible to the requesting admin.

    Args:
        requesting_user: The authenticated admin user
        task_id: Task primary key

    Returns:
        Dictionary with task data or error message
    """
    try:
        task = (
            _admin_visible_tasks(requesting_user)
            .select_related("created_by")
            .get(id=task_id)
        )
        return {"msg": "Task retrieved successfully", "data": _serialize_task(task)}
    except Task.DoesNotExist:
        return {"msg": "Task not found", "data": None}


# ─── mutations ───────────────────────────────────────────────────────────────

@transaction.atomic
def create_admin_task(requesting_user, input_data: dict) -> TaskResponseDict:
    """
    Create a new task as the requesting admin.

    Args:
        requesting_user: The authenticated admin user
        input_data: Task creation fields

    Returns:
        Dictionary with created task or error message
    """
    task_type = input_data.get("task_type")
    group_id = input_data.get("group")
    assigned_user_id = input_data.get("assigned_user")

    if task_type == TaskType.GROUP and not group_id:
        return {"msg": "Group task requires a group", "data": None}
    if task_type == TaskType.INDIVIDUAL and not assigned_user_id:
        return {"msg": "Individual task requires an assigned user", "data": None}

    creator_role = resolve_creator_role(
        requesting_user,
        task_type,
        group=group_id,
        assigned_user=assigned_user_id,
    )

    # §3: only admins with authority over the target track may create via this endpoint
    if creator_role not in (CreatorRole.GLOBAL_ADMIN, CreatorRole.TRACK_ADMIN):
        return {"msg": "You do not have authority to create tasks for this target", "data": None}

    task = Task.objects.create(
        name=(input_data.get("name") or "").strip(),
        description=(input_data.get("description") or "").strip(),
        due_date=input_data.get("due_date") or None,
        status=input_data.get("status") or TaskStatus.TODO,
        task_type=task_type,
        group_id=group_id if task_type == TaskType.GROUP else None,
        assigned_user_id=assigned_user_id if task_type == TaskType.INDIVIDUAL else None,
        parent_id=input_data.get("parent") or None,
        created_by=requesting_user,
        creator_role=creator_role,
    )
    task = Task.objects.select_related("created_by").get(id=task.id)
    return {"msg": "Task created successfully", "data": _serialize_task(task)}


@transaction.atomic
def update_admin_task(requesting_user, task_id: int, input_data: dict) -> TaskResponseDict:
    """
    Update an existing task if the requesting admin has permission.

    Args:
        requesting_user: The authenticated admin user
        task_id: Task primary key
        input_data: Fields to update

    Returns:
        Dictionary with updated task or error message
    """
    try:
        task = (
            _admin_visible_tasks(requesting_user)
            .select_related("created_by")
            .get(id=task_id)
        )
    except Task.DoesNotExist:
        return {"msg": "Task not found", "data": None}

    if "name" in input_data:
        task.name = input_data["name"]
    if "description" in input_data:
        task.description = input_data["description"]
    if "due_date" in input_data:
        task.due_date = input_data["due_date"] or None
    if "status" in input_data:
        task.status = input_data["status"]
    if "parent" in input_data:
        task.parent_id = input_data["parent"] or None

    task.save()
    task = Task.objects.select_related("created_by").get(id=task.id)
    return {"msg": "Task updated successfully", "data": _serialize_task(task)}


@transaction.atomic
def delete_admin_task(requesting_user, task_id: int) -> TaskResponseDict:
    """
    Soft-delete a task if the requesting admin has permission.

    Args:
        requesting_user: The authenticated admin user
        task_id: Task primary key

    Returns:
        Dictionary with success status or error message
    """
    try:
        task = _admin_visible_tasks(requesting_user).get(id=task_id)
    except Task.DoesNotExist:
        return {"msg": "Task not found", "data": None}

    task.soft_delete()
    return {"msg": "Task deleted successfully", "data": True}


@transaction.atomic
def toggle_admin_task(requesting_user, task_id: int, completed: bool) -> TaskResponseDict:
    """
    Toggle the completion state of a task.

    Args:
        requesting_user: The authenticated admin user
        task_id: Task primary key
        completed: New completion state

    Returns:
        Dictionary with updated task or error message
    """
    try:
        task = (
            _admin_visible_tasks(requesting_user)
            .select_related("created_by")
            .get(id=task_id)
        )
    except Task.DoesNotExist:
        return {"msg": "Task not found", "data": None}

    task.completed = completed
    task.save(update_fields=["completed"])
    return {"msg": "Task updated successfully", "data": _serialize_task(task)}
