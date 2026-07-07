from __future__ import annotations

from typing import Iterable, Optional

from django.apps import apps
from rest_framework.permissions import BasePermission

from apps.common.rbac import is_admin

from .rbac import can_access_resource_file


class IsResourceAdmin(BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view) -> bool:
        # Developer note: keep the DRF permission shim thin so resource RBAC logic
        # lives in one helper module instead of drifting between views and classes.
        return is_admin(getattr(request, "user", None))


class IsInAnyGroup(BasePermission):
    """
    Allow access if the authenticated user belongs to ANY of the groups
    specified on the view.

    Usage on a view or viewset:
        class MyAdminView(...):
            permission_classes = [IsInAnyGroup]
            required_groups = ["Admin", "Supervisor"]  # or a single str

    Notes:
    - If no 'required_groups' / 'required_group' attribute is present on the view,
      this permission returns True (no gating).
    - Unauthenticated requests are denied (return False), producing 401 upstream.
    """
    message = "You do not belong to any of the required groups."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        required: Optional[Iterable[str]] = (
            getattr(view, "required_groups", None) or getattr(view, "required_group", None)
        )
        if not required:
            return True

        if isinstance(required, str):
            required = [required]

        return user.groups.filter(name__in=list(required)).exists()


class CanAccessResource(BasePermission):
    """
    Delegate resource visibility checks to the shared resource RBAC helper.
    """
    message = "You do not have access to this resource."

    # ---- Public hooks (optional) ------------------------------------------------
    # Change which URL kwarg identifies the resource:
    resource_lookup_kwarg_candidates = ("resource_id", "pk", "id")

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        resource = self._resolve_resource(request, view)
        if resource is None:
            return True

        return can_access_resource_file(user, resource)

    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        return can_access_resource_file(user, obj)

    # ---- Helpers ----------------------------------------------------------------

    def _extract_resource_id(self, request, view):
        # 1) URL kwarg candidates
        if hasattr(view, "kwargs"):
            for key in getattr(view, "resource_lookup_kwarg_candidates", self.resource_lookup_kwarg_candidates):
                if key in view.kwargs:
                    return view.kwargs[key]
        # 2) Query param
        rid = request.query_params.get("resource_id")
        if rid:
            return rid
        # 3) Try resolving the object (detail views)
        try:
            obj = view.get_object()
            return getattr(obj, "id", None) or getattr(obj, "pk", None)
        except Exception:
            return None

    def _resolve_resource(self, request, view) -> Optional[object]:
        resource_id = self._extract_resource_id(request, view)
        if not resource_id:
            return None

        Resources = apps.get_model("resources", "Resources")
        return Resources.objects.select_related("group", "track").prefetch_related(
            "audiences__role",
            "audiences__track",
        ).filter(pk=resource_id).first()
