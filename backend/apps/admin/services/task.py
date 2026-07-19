from typing import TypedDict, Optional, List, Dict, Any

from django.db import transaction
from django.db.models import Q

from apps.common.rbac import is_admin, users_with_role
from apps.common.role_names import ROLE_ADMIN, try_get_role_by_name
from apps.tasks.models import Task, TaskStatus, TaskType, CreatorRole
from apps.tasks.permissions import resolve_creator_role
from apps.groups.models import Groups, GroupMembership


def _admin_visible_tasks(requesting_user):
    """Tasks visible to an admin — gated on AdminScope, not is_staff/is_superuser."""
    if not is_admin(requesting_user):
        return Task.objects.none()
    return Task.objects.active()


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
    sort_by: str = "createdAt",
    sort_order: str = "desc",
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
    sort_map = {
        "completed": ["completed", "id"],
        "name": ["name", "id"],
        "type": ["task_type", "name", "id"],
        "target": ["group_id", "assigned_user_id", "id"],
        "status": ["status", "name", "id"],
        "due": ["due_date", "id"],
        "createdAt": ["created_at", "id"],
    }
    order_by = sort_map.get(sort_by, sort_map["createdAt"])
    if sort_order == "desc":
        order_by = [f"-{field}" if field != "id" else field for field in order_by]

    qs = (
        _admin_visible_tasks(requesting_user)
        .select_related("created_by")
        .order_by(*order_by)
    )
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

def _shared_task_fields(input_data: dict) -> dict:
    """Content fields common to every creation path, normalized once so the
    single-assignee and role fan-out paths cannot drift apart."""
    return {
        "name": (input_data.get("name") or "").strip(),
        "description": (input_data.get("description") or "").strip(),
        "due_date": input_data.get("due_date") or None,
        "status": input_data.get("status") or TaskStatus.TODO,
        "parent_id": input_data.get("parent") or None,
    }


def _is_targetable_role(role_name: str) -> bool:
    # Validate against the seeded Roles table (as events/announcements/resources
    # do) so a newly-seeded role works without a code change. `admin` is the
    # exception: it comes from AdminScope and need not exist as a Roles row.
    return role_name == ROLE_ADMIN or try_get_role_by_name(role_name) is not None


def count_role_recipients(requesting_user, role_name: str) -> TaskResponseDict:
    """How many users a role fan-out would actually target.

    Exists so the admin sees the resolved count *before* committing hundreds
    of rows — the UI has no bulk undo. It also makes stale role assignments
    visible: if "student" resolves to far fewer people than expected, the
    RoleAssignmentHistory validity windows are the place to look.
    """
    if not is_admin(requesting_user):
        return {"msg": "Not permitted", "data": None}

    normalized = str(role_name or "").strip().lower()
    if not _is_targetable_role(normalized):
        return {"msg": f"Unknown role '{normalized}'", "data": None}

    return {
        "msg": "Recipient count retrieved successfully",
        "data": {
            "role": normalized,
            "count": users_with_role(normalized).count(),
        },
    }


def _create_role_fanout_tasks(
    requesting_user, assigned_role: str, creator_role: str, input_data: dict
) -> TaskResponseDict:
    """Expand a role target into one INDIVIDUAL task per holder of that role.

    Fan-out (rather than a single broadcast row) so each recipient gets their
    own `completed` flag and the existing per-task permission rules apply
    unchanged. Recipients are resolved once, here: someone who gains the role
    later does not retroactively receive the task.

    NOTE: uses bulk_create, so any future Task.save() override or pre/post_save
    signal will NOT fire for these rows.
    """
    if not _is_targetable_role(assigned_role):
        return {
            "msg": f"Unknown role '{assigned_role}'",
            "data": None,
        }

    recipient_ids = list(users_with_role(assigned_role).values_list("id", flat=True))
    if not recipient_ids:
        return {
            "msg": f"No active users currently hold the '{assigned_role}' role",
            "data": None,
        }

    shared = _shared_task_fields(input_data)
    created = Task.objects.bulk_create(
        [
            Task(
                **shared,
                task_type=TaskType.INDIVIDUAL,
                group_id=None,
                assigned_user_id=user_id,
                created_by=requesting_user,
                creator_role=creator_role,
            )
            for user_id in recipient_ids
        ],
        # Postgres does not cap bulk_batch_size, so an unbatched insert would
        # hit the 65535 bind-parameter limit at ~4600 recipients.
        batch_size=500,
    )

    # Deliberately no serialized task list: fanning out to `student` is one row
    # per active student, and no caller reads them.
    return {
        "msg": (
            f"Created {len(created)} tasks for every user with the "
            f"'{assigned_role}' role"
        ),
        "data": {
            "created_count": len(created),
            "assigned_role": assigned_role,
        },
    }


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
    assigned_role = str(input_data.get("assigned_role") or "").strip().lower()

    if task_type == TaskType.GROUP:
        if not group_id:
            return {"msg": "Group task requires a group", "data": None}
        # Reject rather than silently ignore — a caller passing both has a bug.
        if assigned_role:
            return {
                "msg": "Group tasks cannot target a role",
                "data": None,
            }
    if task_type == TaskType.INDIVIDUAL:
        if assigned_role and assigned_user_id:
            return {
                "msg": "Provide either an assigned user or a role, not both",
                "data": None,
            }
        if not assigned_role and not assigned_user_id:
            return {"msg": "Individual task requires an assigned user", "data": None}

    creator_role = resolve_creator_role(
        requesting_user,
        task_type,
        group=group_id,
        assigned_user=assigned_user_id,
    )

    # §3: only admins may create via this endpoint
    if creator_role != CreatorRole.GLOBAL_ADMIN:
        return {"msg": "You do not have authority to create tasks for this target", "data": None}

    if task_type == TaskType.INDIVIDUAL and assigned_role:
        return _create_role_fanout_tasks(
            requesting_user, assigned_role, creator_role, input_data
        )

    task = Task.objects.create(
        **_shared_task_fields(input_data),
        task_type=task_type,
        group_id=group_id if task_type == TaskType.GROUP else None,
        assigned_user_id=assigned_user_id if task_type == TaskType.INDIVIDUAL else None,
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
        # Keep the derived completion flag in lockstep with status so the admin
        # status control is the single source of truth for "done".
        task.completed = input_data["status"] == TaskStatus.DONE
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
