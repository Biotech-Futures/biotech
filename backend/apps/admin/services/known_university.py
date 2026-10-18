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


def add_known_university(name, *, actor=None) -> tuple[dict, int]:
    """Add ``name`` (spacing tidied), unless it's blank, too long or already
    listed in any casing or spacing. Returns the response and its status."""
    if not isinstance(name, str) or not KnownUniversity.normalise(name):
        return _refused("University name is required"), 400
    name = KnownUniversity.normalise(name)
    if len(name) > NAME_MAX_LENGTH:
        return _refused(f"University name must be {NAME_MAX_LENGTH} characters or fewer"), 400
    duplicate = _refused(f"'{name}' is already on the list")
    if KnownUniversity.objects.filter(name__iexact=name).exists():
        return duplicate, 400
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
