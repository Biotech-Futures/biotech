"""Canonical role-name constants and lookup helpers.

All references to business-domain roles SHOULD go through this module instead
of hardcoding numeric primary keys or repeating ``role_name__iexact=...``
queries inline. Role PKs are not stable across environments (they depend on
seed order); role *names* are the contract.

Use ``get_role_by_name`` whenever you need a ``Roles`` row, and the
``ROLE_*`` constants when comparing the active role of a user.
"""
from __future__ import annotations

from typing import Optional

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist


ROLE_ADMIN = "admin"
ROLE_SUPERVISOR = "supervisor"
ROLE_MENTOR = "mentor"
ROLE_STUDENT = "student"
ROLE_BASIC_USER = "basic_user"

NON_STUDENT_ROLES = frozenset({ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_MENTOR, "administrator"})

DEFAULT_ROLE_NAME = ROLE_BASIC_USER


def normalize_role_name(name: Optional[str]) -> str:
    """Return a case/whitespace-normalized role name suitable for comparisons."""
    if not name:
        return ""
    return str(name).strip().lower()


def get_role_by_name(name: str, *, create_missing: bool = False):
    """Look up a ``Roles`` row by name (case-insensitive).

    Set ``create_missing=True`` for bootstrapping/registration flows that
    must succeed even if the seed data hasn't been applied yet. Returns the
    ``Roles`` instance.

    Raises ``Roles.DoesNotExist`` if the role is missing and
    ``create_missing`` is False.
    """
    Roles = apps.get_model("resources", "Roles")
    normalized = (name or "").strip()
    if not normalized:
        raise ValueError("Role name must be a non-empty string")

    role = Roles.objects.filter(role_name__iexact=normalized).first()
    if role is not None:
        return role

    if create_missing:
        role, _ = Roles.objects.get_or_create(
            role_name__iexact=normalized,
            defaults={"role_name": normalized},
        )
        return role

    # Re-raise as the standard Django DoesNotExist so callers can catch it
    # the same way they would for any other model lookup.
    raise Roles.DoesNotExist(f"Role with name {normalized!r} not found")


def try_get_role_by_name(name: str):
    """Like ``get_role_by_name`` but returns ``None`` if the role is missing."""
    try:
        return get_role_by_name(name)
    except (ObjectDoesNotExist, ValueError):
        return None
