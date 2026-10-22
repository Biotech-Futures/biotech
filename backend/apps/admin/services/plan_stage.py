"""Stage CRUD for the admin plan builder (/api/v1/admin/plan-stage/).

One shared stage list for every group's plan. Stages soft-delete, and a stage
that still holds live tasks cannot be deleted. Every mutation is audited with
before/after values so the returning-group checklist can be checked later.
"""
from django.db import models, transaction
from django.utils import timezone

from apps.audit.services import log_audit_event
from apps.plans.models import PlanStage, PlanTask

NAME_MAX_LENGTH = PlanStage._meta.get_field("name").max_length
# The biggest value the field's Postgres integer column can hold; a larger one
# would pass validation and then raise a DataError on insert.
POSITION_MAX = 2_147_483_647
POSITION_FIELDS = ("name", "description", "position")
STAGE_ENTITY_TYPE = "plan_stage"


def _serialize(stage: PlanStage) -> dict:
    return {
        "id": stage.pk,
        "name": stage.name,
        "description": stage.description,
        "position": stage.position,
    }


def _refused(msg: str) -> dict:
    return {"msg": msg, "data": None}


def _checked_text(payload, field, *, required=False, max_length=None):
    """Trimmed string field; returns (value_or_None, refusal). Absent is None."""
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
    """Non-negative integer field; returns (value_or_None, refusal)."""
    if "position" not in payload:
        return default, None
    value = payload["position"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None, _refused("position must be a non-negative whole number")
    if value > POSITION_MAX:
        return None, _refused(f"position must be {POSITION_MAX} or fewer")
    return value, None


def _unknown_fields(payload, allowed) -> dict | None:
    if not isinstance(payload, dict):
        return _refused("Request body must be an object")
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        return _refused(f"Unknown field: {unknown[0]}")
    return None


def list_plan_stages() -> dict:
    """All active stages in plan order, including empty ones.

    Each stage carries ``task_count``: its live task total across the whole
    plan, not just the page the task table is showing, so a populated stage
    never reads as empty.
    """
    stages = list(PlanStage.objects.active())
    counts = dict(
        PlanTask.objects.filter(
            stage__in=stages, deleted_at__isnull=True
        )
        .values_list("stage_id")
        .annotate(total=models.Count("id"))
    )
    return {
        "msg": "Stages retrieved successfully",
        "data": {
            "items": [
                {**_serialize(stage), "task_count": counts.get(stage.pk, 0)}
                for stage in stages
            ]
        },
    }


@transaction.atomic
def create_plan_stage(payload, *, actor=None) -> tuple[dict, int]:
    refusal = _unknown_fields(payload, POSITION_FIELDS)
    if refusal:
        return refusal, 400
    name, refusal = _checked_text(payload, "name", required=True, max_length=NAME_MAX_LENGTH)
    if refusal:
        return refusal, 400
    description, refusal = _checked_text(payload, "description")
    if refusal:
        return refusal, 400
    position, refusal = _checked_position(payload, default=0)
    if refusal:
        return refusal, 400

    stage = PlanStage.objects.create(
        name=name,
        description=description or "",
        position=position,
    )
    log_audit_event(
        actor=actor,
        entity_type=STAGE_ENTITY_TYPE,
        entity_id=stage.pk,
        action="create",
        after_state=_serialize(stage),
    )
    return {"msg": "Stage created successfully", "data": _serialize(stage)}, 201


@transaction.atomic
def update_plan_stage(stage_id: int, payload, *, actor=None) -> tuple[dict, int]:
    refusal = _unknown_fields(payload, POSITION_FIELDS)
    if refusal:
        return refusal, 400
    stage = PlanStage.objects.select_for_update().filter(
        pk=stage_id, deleted_at__isnull=True
    ).first()
    if stage is None:
        return _refused("Stage not found"), 404

    before = _serialize(stage)
    changes = {}
    if "name" in payload:
        name, refusal = _checked_text(payload, "name", required=True, max_length=NAME_MAX_LENGTH)
        if refusal:
            return refusal, 400
        changes["name"] = name
    if "description" in payload:
        description, refusal = _checked_text(payload, "description")
        if refusal:
            return refusal, 400
        changes["description"] = description or ""
    if "position" in payload:
        position, refusal = _checked_position(payload)
        if refusal:
            return refusal, 400
        changes["position"] = position

    changed = [field for field, value in changes.items() if getattr(stage, field) != value]
    if not changed:
        return {"msg": "Stage unchanged", "data": before}, 200

    for field in changed:
        setattr(stage, field, changes[field])
    stage.save(update_fields=[*changed, "updated_at"])
    log_audit_event(
        actor=actor,
        entity_type=STAGE_ENTITY_TYPE,
        entity_id=stage.pk,
        action="update",
        before_state=before,
        after_state=_serialize(stage),
    )
    return {"msg": "Stage updated successfully", "data": _serialize(stage)}, 200


@transaction.atomic
def delete_plan_stage(stage_id: int, *, actor=None) -> tuple[dict, int]:
    stage = PlanStage.objects.select_for_update().filter(
        pk=stage_id, deleted_at__isnull=True
    ).first()
    if stage is None:
        return _refused("Stage not found"), 404
    if PlanTask.objects.filter(stage=stage, deleted_at__isnull=True).exists():
        return _refused(
            "This stage still contains tasks. Remove or delete them first."
        ), 400
    before = _serialize(stage)
    stage.deleted_at = timezone.now()
    stage.save(update_fields=["deleted_at", "updated_at"])
    log_audit_event(
        actor=actor,
        entity_type=STAGE_ENTITY_TYPE,
        entity_id=stage.pk,
        action="delete",
        before_state=before,
        after_state={"id": stage.pk, "deleted_at": stage.deleted_at.isoformat()},
    )
    return {"msg": "Stage deleted successfully", "data": None}, 204
