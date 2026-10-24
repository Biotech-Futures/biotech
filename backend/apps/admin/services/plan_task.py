"""Task CRUD for the admin plan builder (/api/v1/admin/plan-task/).

Tasks belong to one shared plan; ``has_completions`` reports whether any
current-year group holds a completion record (ticked or not), which locks the
task's audience and mode. Edits lock the affected stages (in ID order) before
the task row, then re-read the lock state, following the row-lock protocol in
docs/group-plans-implementation-reference.md so these edits stay consistent
with GP3's completion writes.
"""
import re
from datetime import date
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import F

from apps.audit.services import log_audit_event
from apps.groups.models import GroupMembership
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.plans.visibility import current_plan_groups
from apps.submissions.services import current_cohort

NAME_MAX_LENGTH = PlanTask._meta.get_field("name").max_length
LABEL_MAX_LENGTH = PlanTask._meta.get_field("resource_label").max_length
URL_MAX_LENGTH = PlanTask._meta.get_field("resource_url").max_length
# The biggest value the field's Postgres integer column can hold; a larger one
# would pass validation and then raise a DataError on insert.
POSITION_MAX = 2_147_483_647

AUDIENCE_ROLES = tuple(GroupMembership.MembershipRoleChoices.values)
COMPLETION_MODES = tuple(PlanTask.CompletionMode.values)
DEFAULT_MODE = PlanTask.CompletionMode.PER_PERSON

EDITABLE_FIELDS = (
    "name",
    "description",
    "position",
    "resource_url",
    "resource_label",
    "due_date",
    "audience_role",
    "completion_mode",
    "stage_id",
)
SORT_KEYS = ("position", "name", "due", "createdAt")
_DUE_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TASK_ENTITY_TYPE = "plan_task"


def _serialize(task: PlanTask, *, has_completions: bool) -> dict:
    created_by = None
    if task.created_by_id and task.created_by:
        user = task.created_by
        name = f"{user.first_name} {user.last_name}".strip() or None
        created_by = {"id": user.id, "name": name}
    return {
        "id": task.pk,
        "stage_id": task.stage_id,
        "position": task.position,
        "name": task.name,
        "description": task.description,
        "resource_url": task.resource_url,
        "resource_label": task.resource_label,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "audience_role": task.audience_role,
        "completion_mode": task.completion_mode,
        "has_completions": has_completions,
        "created_by": created_by,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _refused(msg: str) -> dict:
    return {"msg": msg, "data": None}


def _has_completions(task: PlanTask, year: int) -> bool:
    """Any record for this task in a current-year group, even unticked."""
    return PlanTaskCompletion.objects.filter(
        task=task, group__in=current_plan_groups(year)
    ).exists()


def _ids_with_completions(task_ids, year: int) -> set:
    """One query for a whole page: which of these tasks a group has recorded."""
    return set(
        PlanTaskCompletion.objects.filter(
            task_id__in=task_ids, group__in=current_plan_groups(year)
        ).values_list("task_id", flat=True)
    )


# ─── field validation ────────────────────────────────────────────────────────


def _unknown_field_refusal(payload) -> dict | None:
    if not isinstance(payload, dict):
        return _refused("Request body must be an object")
    unknown = sorted(set(payload) - set(EDITABLE_FIELDS))
    if unknown:
        return _refused(f"Unknown field: {unknown[0]}")
    return None


def _checked_text(payload, field, *, required=False, max_length=None):
    if field not in payload:
        if required:
            return None, _refused(f"{field} is required")
        return None, None
    value = payload[field]
    if not isinstance(value, str):
        return None, _refused(f"{field} must be text")
    value = value.strip()
    if required and not value:
        return None, _refused(f"{field} is required")
    if max_length is not None and len(value) > max_length:
        return None, _refused(f"{field} must be {max_length} characters or fewer")
    return value, None


def _checked_position(payload, *, default=None):
    if "position" not in payload:
        return default, None
    value = payload["position"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None, _refused("position must be a non-negative whole number")
    if value > POSITION_MAX:
        return None, _refused(f"position must be {POSITION_MAX} or fewer")
    return value, None


def _checked_due_date(value):
    if value is None:
        return None, None
    if not isinstance(value, str) or not _DUE_DATE_PATTERN.match(value):
        return None, _refused("due_date must be a date in YYYY-MM-DD format, or null")
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, _refused("due_date must be a real calendar date")


def _checked_resource_pair(url: str, label: str) -> str | None:
    """A task has either both a resource link and label, or neither."""
    if bool(url) != bool(label):
        return "A resource needs both a link and a label (or neither)."
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "The resource link must be a valid http:// or https:// address."
    return None


def _validate_fields(payload, *, partial: bool) -> tuple[dict | None, dict | None]:
    """Type/range checks only; resource-pair and stage checks happen under lock."""
    cleaned = {}
    if "name" in payload or not partial:
        name, refusal = _checked_text(payload, "name", required=True, max_length=NAME_MAX_LENGTH)
        if refusal:
            return None, refusal
        cleaned["name"] = name
    if "description" in payload or not partial:
        description, refusal = _checked_text(payload, "description")
        if refusal:
            return None, refusal
        cleaned["description"] = description or ""
    if "position" in payload or not partial:
        position, refusal = _checked_position(payload, default=0 if not partial else None)
        if refusal:
            return None, refusal
        cleaned["position"] = position
    if "resource_url" in payload or not partial:
        url, refusal = _checked_text(payload, "resource_url", max_length=URL_MAX_LENGTH)
        if refusal:
            return None, refusal
        cleaned["resource_url"] = url or ""
    if "resource_label" in payload or not partial:
        label, refusal = _checked_text(payload, "resource_label", max_length=LABEL_MAX_LENGTH)
        if refusal:
            return None, refusal
        cleaned["resource_label"] = label or ""
    if "due_date" in payload or not partial:
        raw = payload["due_date"] if "due_date" in payload else None
        due_date, refusal = _checked_due_date(raw)
        if refusal:
            return None, refusal
        cleaned["due_date"] = due_date
    if "audience_role" in payload or not partial:
        value = payload.get("audience_role") if "audience_role" in payload else None
        if value is None:
            return None, _refused("audience_role is required")
        if not isinstance(value, str) or value not in AUDIENCE_ROLES:
            return None, _refused("audience_role must be student, mentor or supervisor")
        cleaned["audience_role"] = value
    if "completion_mode" in payload or not partial:
        value = payload.get("completion_mode") if "completion_mode" in payload else DEFAULT_MODE
        if value is None:
            value = DEFAULT_MODE
        if not isinstance(value, str) or value not in COMPLETION_MODES:
            return None, _refused("completion_mode must be per_person or per_group")
        cleaned["completion_mode"] = value
    if "stage_id" in payload or not partial:
        if "stage_id" not in payload:
            return None, _refused("stage_id is required")
        value = payload["stage_id"]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None, _refused("stage_id must be the ID of a stage")
        cleaned["stage_id"] = value
    return cleaned, None


# ─── list / detail ───────────────────────────────────────────────────────────


def _checked_int_param(value, *, default: int, maximum: int | None = None):
    if value is None or value == "":
        return default, None
    if isinstance(value, bool):
        return None, _refused("Query values must be whole numbers")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        return None, _refused("Query values must be whole numbers")
    if parsed < 1:
        return None, _refused("Query values must be positive whole numbers")
    if maximum is not None and parsed > maximum:
        return None, _refused(f"Query values must be {maximum} or fewer")
    return parsed, None


def _checked_stage_id_param(value):
    """Optional ``stage_id`` filter: a positive whole number, or None."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, _refused("stage_id must be the ID of a stage")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        return None, _refused("stage_id must be the ID of a stage")
    if parsed <= 0:
        return None, _refused("stage_id must be the ID of a stage")
    return parsed, None


def list_plan_tasks(
    *, page=None, limit=None, sort_by=None, sort_order=None, stage_id=None
) -> tuple[dict, int]:
    page, refusal = _checked_int_param(page, default=1)
    if refusal:
        return refusal, 400
    limit, refusal = _checked_int_param(limit, default=10, maximum=100)
    if refusal:
        return refusal, 400
    if sort_by is None or sort_by == "":
        sort_by = "position"
    elif sort_by not in SORT_KEYS:
        return _refused(f"sortBy must be one of {', '.join(SORT_KEYS)}"), 400
    if sort_order is None or sort_order == "":
        sort_order = "asc"
    elif sort_order not in ("asc", "desc"):
        return _refused("sortOrder must be asc or desc"), 400
    stage_id, refusal = _checked_stage_id_param(stage_id)
    if refusal:
        return refusal, 400

    qs = PlanTask.objects.active().select_related("stage", "created_by")
    if stage_id is not None:
        qs = qs.filter(stage_id=stage_id)
    descending = sort_order == "desc"
    if sort_by == "name":
        qs = qs.order_by("-name" if descending else "name", "id")
    elif sort_by == "due":
        due = F("due_date").desc(nulls_last=True) if descending else F("due_date").asc(nulls_last=True)
        qs = qs.order_by(due, "id")
    elif sort_by == "createdAt":
        qs = qs.order_by("-created_at" if descending else "created_at", "id")
    elif descending:
        qs = qs.order_by("-stage__position", "-stage_id", "-position", "-id")
    else:
        qs = qs.in_plan_order()

    offset = (page - 1) * limit
    total = qs.count()
    items = list(qs[offset : offset + limit])
    locked_ids = _ids_with_completions([task.pk for task in items], current_cohort())
    has_more = offset + len(items) < total
    return (
        {
            "msg": "Tasks retrieved successfully",
            "data": {
                "items": [
                    _serialize(task, has_completions=task.pk in locked_ids)
                    for task in items
                ],
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": has_more,
            },
        },
        200,
    )


def get_plan_task(task_id: int) -> tuple[dict, int]:
    task = PlanTask.objects.filter(pk=task_id).first()
    if task is None or task.deleted_at is not None:
        return _refused("Task not found"), 404
    return (
        {
            "msg": "Task retrieved successfully",
            "data": _serialize(task, has_completions=_has_completions(task, current_cohort())),
        },
        200,
    )


# ─── create / update / delete ────────────────────────────────────────────────


@transaction.atomic
def create_plan_task(payload, *, actor=None) -> tuple[dict, int]:
    refusal = _unknown_field_refusal(payload)
    if refusal:
        return refusal, 400
    cleaned, refusal = _validate_fields(payload, partial=False)
    if refusal:
        return refusal, 400
    pair_error = _checked_resource_pair(cleaned["resource_url"], cleaned["resource_label"])
    if pair_error:
        return _refused(pair_error), 400

    stage_id = cleaned.pop("stage_id")
    # Lock the target stage so it cannot be deleted between the check and the insert.
    stage = PlanStage.objects.select_for_update().filter(pk=stage_id).first()
    if stage is None or stage.deleted_at is not None:
        return _refused("Select a stage that has not been deleted"), 400

    task = PlanTask.objects.create(
        stage=stage,
        created_by=actor if getattr(actor, "pk", None) else None,
        **cleaned,
    )
    log_audit_event(
        actor=actor,
        entity_type=TASK_ENTITY_TYPE,
        entity_id=task.pk,
        action="create",
        after_state=_serialize(task, has_completions=False),
    )
    return {"msg": "Task created successfully", "data": _serialize(task, has_completions=False)}, 201


@transaction.atomic
def update_plan_task(task_id: int, payload, *, actor=None) -> tuple[dict, int]:
    refusal = _unknown_field_refusal(payload)
    if refusal:
        return refusal, 400
    existing = PlanTask.objects.filter(pk=task_id).first()
    if existing is None or existing.deleted_at is not None:
        return _refused("Task not found"), 404
    cleaned, refusal = _validate_fields(payload, partial=True)
    if refusal:
        return refusal, 400

    stage_ids = {existing.stage_id}
    if "stage_id" in cleaned:
        stage_ids.add(cleaned["stage_id"])
    # Stage locks come first, in ID order, then the task row — the same order
    # GP3's completion writes and any concurrent move will follow.
    stages = {
        stage.pk: stage
        for stage in PlanStage.objects.select_for_update()
        .filter(pk__in=stage_ids)
        .order_by("pk")
    }
    if "stage_id" in cleaned:
        target = stages.get(cleaned["stage_id"])
        if target is None or target.deleted_at is not None:
            return _refused("Select a stage that has not been deleted"), 400
    task = PlanTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None or task.deleted_at is not None:
        return _refused("Task not found"), 404
    if task.stage_id not in stages:
        # A concurrent move changed the stage between our first read and the
        # locks; the locked set no longer matches, so ask for a retry rather
        # than acquiring locks out of order.
        return _refused("The task changed while it was being edited. Please try again."), 400

    url = cleaned.get("resource_url", task.resource_url)
    label = cleaned.get("resource_label", task.resource_label)
    pair_error = _checked_resource_pair(url, label)
    if pair_error:
        return _refused(pair_error), 400

    has_completions = _has_completions(task, current_cohort())
    if has_completions:
        if "audience_role" in cleaned and cleaned["audience_role"] != task.audience_role:
            return _refused(
                "Audience cannot be changed once a group has a completion record for this task."
            ), 400
        if "completion_mode" in cleaned and cleaned["completion_mode"] != task.completion_mode:
            return _refused(
                "Completion mode cannot be changed once a group has a completion record for this task."
            ), 400

    before = _serialize(task, has_completions=has_completions)
    update_fields = []
    for field, value in cleaned.items():
        if field == "stage_id":
            if task.stage_id != value:
                task.stage = stages[value]
                update_fields.append("stage")
        elif getattr(task, field) != value:
            setattr(task, field, value)
            update_fields.append(field)
    if not update_fields:
        return {"msg": "Task unchanged", "data": before}, 200
    task.save(update_fields=[*update_fields, "updated_at"])
    log_audit_event(
        actor=actor,
        entity_type=TASK_ENTITY_TYPE,
        entity_id=task.pk,
        action="update",
        before_state=before,
        after_state=_serialize(task, has_completions=has_completions),
    )
    return (
        {"msg": "Task updated successfully", "data": _serialize(task, has_completions=has_completions)},
        200,
    )


@transaction.atomic
def delete_plan_task(task_id: int, *, actor=None) -> tuple[dict, int]:
    existing = PlanTask.objects.filter(pk=task_id).first()
    if existing is None or existing.deleted_at is not None:
        return _refused("Task not found"), 404
    task = PlanTask.objects.select_for_update().get(pk=task_id)
    if task.deleted_at is not None:
        return _refused("Task not found"), 404
    before = _serialize(task, has_completions=_has_completions(task, current_cohort()))
    log_audit_event(
        actor=actor,
        entity_type=TASK_ENTITY_TYPE,
        entity_id=task.pk,
        action="delete",
        before_state=before,
    )
    task.soft_delete()
    return {"msg": "Task deleted successfully", "data": None}, 204
