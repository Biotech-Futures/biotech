"""The list of known universities, for admins
(/api/v1/admin/known-university/). A school name matching one's full name or
acronym, ignoring case and spacing, gets the registration school warning
(apps.users.serializers.registration_warnings)."""
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.audit.services import log_audit_event
from apps.users.models import KnownUniversity

NAME_MAX_LENGTH = KnownUniversity._meta.get_field("full_name").max_length
ACRONYM_MAX_LENGTH = KnownUniversity._meta.get_field("acronym").max_length
COUNTRY_MAX_LENGTH = KnownUniversity._meta.get_field("country").max_length
# A field a PATCH leaves out, which keeps its value.
MISSING = object()


def _serialize(university: KnownUniversity) -> dict:
    return {
        "id": university.pk,
        "fullName": university.full_name,
        "acronym": university.acronym,
        "country": university.country,
        # The page from before full names and acronyms reads this.
        "name": university.full_name,
        "createdAt": university.created_at.isoformat() if university.created_at else None,
        "updatedAt": university.updated_at.isoformat() if university.updated_at else None,
    }


def _state(university: KnownUniversity) -> dict:
    return {"name": university.full_name, "acronym": university.acronym, "country": university.country}


def _refused(msg: str) -> dict:
    return {"msg": msg, "data": None}


def list_known_universities(search=None) -> dict:
    """Every known university, by full name; with ``search``, those whose
    full name, acronym or country contains it, ignoring case."""
    universities = KnownUniversity.objects.all()
    search = (search or "").strip()
    if search:
        universities = universities.filter(
            Q(full_name__icontains=search) | Q(acronym__icontains=search) | Q(country__icontains=search)
        )
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
    if KnownUniversity.objects.filter(full_name__iexact=name).exclude(pk=other_than).exists():
        return name, _refused(f"'{name}' is already on the list")
    return name, None


def _checked_optional(value, label: str, max_length: int) -> tuple[str, dict | None]:
    """An optional acronym or country, spacing tidied; None or "" clears it."""
    if value is None:
        return "", None
    if not isinstance(value, str):
        return "", _refused(f"{label} must be text")
    value = KnownUniversity.normalise(value)
    if len(value) > max_length:
        return value, _refused(f"{label} must be {max_length} characters or fewer")
    return value, None


def add_known_university(name, *, acronym=None, country=None, actor=None) -> tuple[dict, int]:
    """Add ``name`` (spacing tidied), unless it's blank, too long or already
    listed in any casing or spacing, with an optional acronym and country.
    Returns the response and its status."""
    name, refusal = _checked_name(name)
    if refusal:
        return refusal, 400
    acronym, refusal = _checked_optional(acronym, "Acronym", ACRONYM_MAX_LENGTH)
    if refusal:
        return refusal, 400
    country, refusal = _checked_optional(country, "Country", COUNTRY_MAX_LENGTH)
    if refusal:
        return refusal, 400
    duplicate = _refused(f"'{name}' is already on the list")
    try:
        with transaction.atomic():
            university = KnownUniversity.objects.create(full_name=name, acronym=acronym, country=country)
            log_audit_event(
                actor=actor, entity_type="known_university", entity_id=university.pk,
                action="create", after_state=_state(university),
            )
    except IntegrityError:
        # Added by someone else since the check above.
        return duplicate, 400
    return {"msg": "Known university added successfully", "data": _serialize(university)}, 201


def rename_known_university(
    university_id: int, name=MISSING, *, acronym=MISSING, country=MISSING, actor=None,
) -> tuple[dict, int]:
    """Change a university's full name, acronym or country; a field left out
    keeps its value. The full name is checked as an added one is (its own
    name in another casing is fine). Returns the response and its status."""
    if name is MISSING and acronym is MISSING and country is MISSING:
        return _refused("University name is required"), 400
    with transaction.atomic():
        university = KnownUniversity.objects.select_for_update().filter(pk=university_id).first()
        if university is None:
            return _refused("Known university not found"), 404
        values = {"full_name": university.full_name, "acronym": university.acronym, "country": university.country}
        if name is not MISSING:
            values["full_name"], refusal = _checked_name(name, other_than=university.pk)
            if refusal:
                return refusal, 400
        for field, value, label, max_length in (
            ("acronym", acronym, "Acronym", ACRONYM_MAX_LENGTH),
            ("country", country, "Country", COUNTRY_MAX_LENGTH),
        ):
            if value is not MISSING:
                values[field], refusal = _checked_optional(value, label, max_length)
                if refusal:
                    return refusal, 400
        if all(getattr(university, field) == value for field, value in values.items()):
            return {"msg": "Known university unchanged", "data": _serialize(university)}, 200
        before = _state(university)
        try:
            with transaction.atomic():
                for field, value in values.items():
                    setattr(university, field, value)
                university.save(update_fields=[*values, "updated_at"])
        except IntegrityError:
            # Added by someone else since the check above.
            return _refused(f"'{values['full_name']}' is already on the list"), 400
        log_audit_event(
            actor=actor, entity_type="known_university", entity_id=university.pk,
            action="update", before_state=before, after_state=_state(university),
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
            action="delete", before_state=_state(university),
        )
        university.delete()
    return {"msg": "Known university deleted successfully", "data": True}, 200
