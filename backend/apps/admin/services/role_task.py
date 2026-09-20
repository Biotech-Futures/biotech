from typing import TypedDict, Optional, List, Dict, Any, Tuple

from django.db import transaction

from apps.common.rbac import is_admin, users_with_role
from apps.common.role_names import ROLE_ADMIN, try_get_role_by_name
from apps.tasks.models import RoleTask, RoleTaskCompletion, CreatorRole


def _admin_visible_role_tasks():
    """RoleTask definitions are global admin bookkeeping — no per-user scoping
    needed, unlike Task's group/individual visibility rules."""
    return RoleTask.objects.active().select_related("role", "created_by")


def _completion_progress(role_tasks: List[RoleTask]) -> Dict[int, Tuple[int, int]]:
    """{role_task_id: (completed_count, holder_count)}, counting only users who
    CURRENTLY hold the role — a completion from someone who has since lost the
    role still exists (see RoleTaskCompletion), but doesn't count toward "how
    many current holders are done".

    Bounded query cost regardless of page size: one `users_with_role` query
    per DISTINCT role on the page (not per row), plus one aggregate query for
    every completion row across the whole page.
    """
    if not role_tasks:
        return {}

    role_names = {rt.role.role_name for rt in role_tasks if rt.role_id}
    holder_ids_by_role = {
        role_name: set(users_with_role(role_name).values_list("id", flat=True))
        for role_name in role_names
    }

    completed_user_ids_by_task: Dict[int, set] = {}
    completions = RoleTaskCompletion.objects.filter(
        role_task_id__in=[rt.id for rt in role_tasks], completed=True
    ).values_list("role_task_id", "user_id")
    for role_task_id, user_id in completions:
        completed_user_ids_by_task.setdefault(role_task_id, set()).add(user_id)

    progress = {}
    for rt in role_tasks:
        holder_ids = holder_ids_by_role.get(rt.role.role_name, set()) if rt.role_id else set()
        completed_ids = completed_user_ids_by_task.get(rt.id, set())
        progress[rt.id] = (len(completed_ids & holder_ids), len(holder_ids))
    return progress


# Type definitions
class RoleTaskDict(TypedDict):
    id: int
    name: str
    description: str
    due_date: Optional[str]
    role: Optional[Dict[str, Any]]
    created_by: Optional[Dict[str, Any]]
    creator_role: str
    deleted_at: Optional[str]
    created_at: str
    updated_at: str
    completed_count: int
    holder_count: int


class RoleTaskResponseDict(TypedDict):
    msg: str
    data: Optional[Any]


# ─── helpers ────────────────────────────────────────────────────────────────

def _serialize_role_task(role_task: RoleTask, progress: Optional[Tuple[int, int]] = None) -> RoleTaskDict:
    created_by = None
    if role_task.created_by_id and role_task.created_by:
        user = role_task.created_by
        name = f"{user.first_name} {user.last_name}".strip() or None
        created_by = {"id": user.id, "name": name}

    role = None
    if role_task.role_id and role_task.role:
        role = {"id": role_task.role.id, "roleName": role_task.role.role_name}

    completed_count, holder_count = progress if progress is not None else (0, 0)

    return {
        "id": role_task.id,
        "name": role_task.name,
        "description": role_task.description,
        "due_date": role_task.due_date.isoformat() if role_task.due_date else None,
        "role": role,
        "created_by": created_by,
        "creator_role": role_task.creator_role,
        "deleted_at": role_task.deleted_at.isoformat() if role_task.deleted_at else None,
        "created_at": role_task.created_at.isoformat(),
        "updated_at": role_task.updated_at.isoformat(),
        "completed_count": completed_count,
        "holder_count": holder_count,
    }


def _is_targetable_role(role_name: str) -> bool:
    # Validate against the seeded Roles table (as events/announcements/resources
    # do) so a newly-seeded role works without a code change. `admin` is the
    # exception: it comes from AdminScope and need not exist as a Roles row.
    return role_name == ROLE_ADMIN or try_get_role_by_name(role_name) is not None


# ─── queries ─────────────────────────────────────────────────────────────────

def list_admin_role_tasks(
    requesting_user,
    page: int = 1,
    limit: int = 10,
    sort_by: str = "createdAt",
    sort_order: str = "desc",
) -> RoleTaskResponseDict:
    """List role-task definitions visible to the requesting admin."""
    if not is_admin(requesting_user):
        return {"msg": "Not permitted", "data": None}

    sort_map = {
        "name": ["name", "id"],
        "role": ["role__role_name", "id"],
        "due": ["due_date", "id"],
        "createdAt": ["created_at", "id"],
    }
    order_by = sort_map.get(sort_by, sort_map["createdAt"])
    if sort_order == "desc":
        order_by = [f"-{field}" if field != "id" else field for field in order_by]

    qs = _admin_visible_role_tasks().order_by(*order_by)

    offset = (page - 1) * limit
    total = qs.count()
    page_items = list(qs[offset:offset + limit])
    progress_by_id = _completion_progress(page_items)
    items = [_serialize_role_task(rt, progress_by_id.get(rt.id)) for rt in page_items]
    has_more = offset + len(items) < total

    return {
        "msg": "Role tasks retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


def get_admin_role_task_by_id(requesting_user, role_task_id: int) -> RoleTaskResponseDict:
    if not is_admin(requesting_user):
        return {"msg": "Not permitted", "data": None}
    try:
        role_task = _admin_visible_role_tasks().get(id=role_task_id)
        progress = _completion_progress([role_task]).get(role_task.id)
        return {"msg": "Role task retrieved successfully", "data": _serialize_role_task(role_task, progress)}
    except RoleTask.DoesNotExist:
        return {"msg": "Role task not found", "data": None}


def count_role_recipients(requesting_user, role_name: str) -> RoleTaskResponseDict:
    """How many users currently hold `role_name` — shown in the admin form
    before it commits a role task that every one of them will pick up."""
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


# ─── mutations ───────────────────────────────────────────────────────────────

@transaction.atomic
def create_admin_role_task(requesting_user, input_data: dict) -> RoleTaskResponseDict:
    """Create a role-task definition — a single row that every current AND
    future holder of the role picks up (visibility is a live join, see
    apps.tasks.role_task_views), rather than one row per current holder."""
    if not is_admin(requesting_user):
        return {"msg": "You do not have authority to create role tasks", "data": None}

    role_name = str(input_data.get("role") or "").strip().lower()
    if not role_name:
        return {"msg": "Role task requires a role", "data": None}
    if not _is_targetable_role(role_name):
        return {"msg": f"Unknown role '{role_name}'", "data": None}

    # RoleTask.role is a real FK to the Roles table, so — same constraint
    # EventTargetRole/ResourceAudience already live with — a role only accepted
    # by `_is_targetable_role` because of the AdminScope special case (i.e.
    # "admin" with no seeded Roles row) still can't be targeted here.
    role_row = try_get_role_by_name(role_name)
    if role_row is None:
        return {"msg": f"Role '{role_name}' is not seeded in the Roles table", "data": None}

    role_task = RoleTask.objects.create(
        name=(input_data.get("name") or "").strip(),
        description=(input_data.get("description") or "").strip(),
        due_date=input_data.get("due_date") or None,
        role=role_row,
        created_by=requesting_user,
        creator_role=CreatorRole.GLOBAL_ADMIN,
    )
    role_task = RoleTask.objects.select_related("role", "created_by").get(id=role_task.id)
    progress = _completion_progress([role_task]).get(role_task.id)
    return {"msg": "Role task created successfully", "data": _serialize_role_task(role_task, progress)}


@transaction.atomic
def update_admin_role_task(requesting_user, role_task_id: int, input_data: dict) -> RoleTaskResponseDict:
    """Edit the one definition row — this is the "bulk-edit in one place":
    every current and future holder of the role sees the update immediately,
    with no per-user rows to touch."""
    if not is_admin(requesting_user):
        return {"msg": "You do not have authority to edit role tasks", "data": None}

    try:
        role_task = _admin_visible_role_tasks().get(id=role_task_id)
    except RoleTask.DoesNotExist:
        return {"msg": "Role task not found", "data": None}

    if "name" in input_data:
        role_task.name = input_data["name"]
    if "description" in input_data:
        role_task.description = input_data["description"]
    if "due_date" in input_data:
        role_task.due_date = input_data["due_date"] or None

    role_task.save()
    role_task = RoleTask.objects.select_related("role", "created_by").get(id=role_task.id)
    progress = _completion_progress([role_task]).get(role_task.id)
    return {"msg": "Role task updated successfully", "data": _serialize_role_task(role_task, progress)}


@transaction.atomic
def delete_admin_role_task(requesting_user, role_task_id: int) -> RoleTaskResponseDict:
    if not is_admin(requesting_user):
        return {"msg": "You do not have authority to delete role tasks", "data": None}

    try:
        role_task = _admin_visible_role_tasks().get(id=role_task_id)
    except RoleTask.DoesNotExist:
        return {"msg": "Role task not found", "data": None}

    role_task.soft_delete()
    return {"msg": "Role task deleted successfully", "data": True}
