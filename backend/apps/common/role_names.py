"""Canonical role-name constants and lookup helpers.

The four role names below mirror the values seeded into
``apps_resources.Roles.role_name`` by data migrations and by
``create_test_users.py``. They also match the lowercase strings returned
by ``apps.common.rbac.active_role_names``.

Why these constants exist:

* Views that need to fetch a role by name (e.g. ``UserRegisterView``
  assigning a freshly registered student to ``role_id=4``) historically
  hardcoded primary keys like ``get_object_or_404(Roles, pk=4)``. That
  couples view logic to a brittle ordering of the seed data. Looking up
  by name via :func:`get_role_by_name` is the safer pattern.
* Comparisons against ``active_role_names(user)`` should use these
  constants instead of bare string literals so a rename in the DB is a
  single-file change here.
"""

from __future__ import annotations

from django.apps import apps


ROLE_ADMIN = "admin"
ROLE_SUPERVISOR = "supervisor"
ROLE_MENTOR = "mentor"
ROLE_STUDENT = "student"


ALL_ROLES: frozenset[str] = frozenset({
    ROLE_ADMIN,
    ROLE_SUPERVISOR,
    ROLE_MENTOR,
    ROLE_STUDENT,
})


def get_role_by_name(name: str):
    """Return the ``Roles`` row whose ``role_name`` matches ``name``.

    Case-insensitive: ``Role.role_name`` is stored lowercase in seed data
    but callers may pass mixed-case strings. Lookup goes through
    ``django.apps.get_model`` (rather than a top-level
    ``from apps.resources.models import Roles`` import) so this module is
    safe to import at any point in the Django app-loading lifecycle —
    matching the pattern used in ``apps/common/rbac.py``.

    Raises ``Roles.DoesNotExist`` if the role is not seeded. We deliberately
    don't return ``None`` or 404 here: a missing core role is a deploy
    misconfiguration that should fail loud, not silently degrade.
    """
    Roles = apps.get_model("resources", "Roles")
    return Roles.objects.get(role_name__iexact=name)
