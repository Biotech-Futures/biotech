"""The list of known universities, for admins
(/api/v1/admin/known-university/). A school name matching one, ignoring case
and spacing, gets the registration school warning
(apps.users.serializers.registration_warnings)."""
from django.db import IntegrityError, transaction

from apps.audit.services import log_audit_event
from apps.users.models import KnownUniversity

NAME_MAX_LENGTH = KnownUniversity._meta.get_field("name").max_length


def _serialize(university: KnownUniversity) -> dict:
    return {
        "id": university.pk,
        "name": university.name,
        "createdAt": university.created_at.isoformat() if university.created_at else None,
    }


def _refused(msg: str) -> dict:
    return {"msg": msg, "data": None}


def list_known_universities(search=None) -> dict:
    """Every known university, by name; with ``search``, those whose name
    contains it, ignoring case."""
    universities = KnownUniversity.objects.all()
    search = (search or "").strip()
    if search:
        universities = universities.filter(name__icontains=search)
    items = [_serialize(university) for university in universities]
    return {
        "msg": "Known universities retrieved successfully",
        "data": {"items": items, "total": len(items)},
    }


def _checked_name(name, *, other_than=None) -> tuple[str, dict | None]:
    """``name`` with its spacing tidied, and why it's refused (or None): blank,
    too long, or already listed in any casing (``other_than`` aside, the one
    being renamed)."""
    if not isinstance(name, str) or not KnownUniversity.normalise(name):
        return "", _refused("University name is required")
    name = KnownUniversity.normalise(name)
    if len(name) > NAME_MAX_LENGTH:
        return name, _refused(f"University name must be {NAME_MAX_LENGTH} characters or fewer")
    if KnownUniversity.objects.filter(name__iexact=name).exclude(pk=other_than).exists():
        return name, _refused(f"'{name}' is already on the list")
    return name, None


def add_known_university(name, *, actor=None) -> tuple[dict, int]:
    """Add ``name`` (spacing tidied), unless it's blank, too long or already
    listed in any casing or spacing. Returns the response and its status."""
    name, refusal = _checked_name(name)
    if refusal:
        return refusal, 400
    duplicate = _refused(f"'{name}' is already on the list")
    try:
        with transaction.atomic():
            university = KnownUniversity.objects.create(name=name)
            log_audit_event(
                actor=actor, entity_type="known_university", entity_id=university.pk,
                action="create", after_state={"name": university.name},
            )
    except IntegrityError:
        # Added by someone else since the check above.
        return duplicate, 400
    return {"msg": "Known university added successfully", "data": _serialize(university)}, 201


def rename_known_university(university_id: int, name, *, actor=None) -> tuple[dict, int]:
    """Rename a university on the list, checked as an added name is (its own
    name in another casing is fine). Returns the response and its status."""
    with transaction.atomic():
        university = KnownUniversity.objects.select_for_update().filter(pk=university_id).first()
        if university is None:
            return _refused("Known university not found"), 404
        name, refusal = _checked_name(name, other_than=university.pk)
        if refusal:
            return refusal, 400
        if name == university.name:
            return {"msg": "Known university unchanged", "data": _serialize(university)}, 200
        before = university.name
        try:
            with transaction.atomic():
                university.name = name
                university.save(update_fields=["name"])
        except IntegrityError:
            # Added by someone else since the check above.
            return _refused(f"'{name}' is already on the list"), 400
        log_audit_event(
            actor=actor, entity_type="known_university", entity_id=university.pk,
            action="update", before_state={"name": before}, after_state={"name": university.name},
        )
    return {"msg": "Known university renamed successfully", "data": _serialize(university)}, 200


def delete_known_university(university_id: int, *, actor=None) -> tuple[dict, int]:
    """Take a university off the list. Returns the response and its status."""
    with transaction.atomic():
        university = KnownUniversity.objects.select_for_update().filter(pk=university_id).first()
        if university is None:
            return _refused("Known university not found"), 404
        log_audit_event(
            actor=actor, entity_type="known_university", entity_id=university.pk,
            action="delete", before_state={"name": university.name},
        )
        university.delete()
    return {"msg": "Known university deleted successfully", "data": True}, 200
