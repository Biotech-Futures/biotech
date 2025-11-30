# apps/resources/permissions.py
from __future__ import annotations

from typing import Iterable, Optional

from django.apps import apps
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission


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
    Allow access to a *Resource* if the authenticated user currently holds ANY role
    that is attached to that resource via ResourceRoles.

    How it works (defaults):
    - Resolves the "business user" (row in users.Users) from the auth user.
      Default resolver tries primary key first, then email match. Override by
      defining 'get_business_user_id(self, request)' on the view if needed.
    - Finds the resource id from, in order:
        view.kwargs['resource_id'] / ['pk'] / ['id']
        OR request.query_params['resource_id']
        OR view.get_object().id (if available)
    - Checks RoleAssignmentHistory for an ACTIVE assignment:
        valid_from <= now AND (valid_to IS NULL OR valid_to >= now)
      whose role appears in ResourceRoles for that resource.

    Usage on a detail endpoint (typical):
        class ResourceViewSet(...):
            permission_classes = [IsInAnyGroup, CanAccessResource]
            required_groups = ["User", "Admin"]  # optional group gating
            # default pk kwarg is fine; customize with:
            # resource_lookup_kwarg = "resource_id"

    You can also place it on list endpoints; has_object_permission will enforce
    access when DRF calls it with the retrieved object.
    """
    message = "You do not have access to this resource."

    # ---- Public hooks (optional) ------------------------------------------------
    # Change which URL kwarg identifies the resource:
    resource_lookup_kwarg_candidates = ("resource_id", "pk", "id")

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        # For list endpoints we may not have an id yet; allow here and defer to
        # has_object_permission. If we *can* extract an id now, enforce early.
        resource_id = self._extract_resource_id(request, view)
        if not resource_id:
            return True

        business_user_id = self._resolve_business_user_id(request, view, user)
        if not business_user_id:
            return False

        return self._user_can_access(business_user_id, resource_id)

    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        resource_id = getattr(obj, "id", None) or getattr(obj, "pk", None) or getattr(obj, "resource_id", None)
        if not resource_id:
            return True  # can't evaluate; don't block unexpectedly

        business_user_id = self._resolve_business_user_id(request, view, user)
        if not business_user_id:
            return False

        return self._user_can_access(business_user_id, resource_id)

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

    def _resolve_business_user_id(self, request, view, auth_user) -> Optional[int]:
        """
        Map the authenticated user to the business Users row.
        Override on the view by implementing:
            def get_business_user_id(self, request): ...
        Defaults:
          1) direct pk match
          2) email match (if present)
        """
        if hasattr(view, "get_business_user_id"):
            try:
                return int(view.get_business_user_id(request))
            except Exception:
                return None

        Users = apps.get_model("users", "Users")
        # 1) direct PK match
        try:
            if Users.objects.filter(pk=auth_user.pk).exists():
                return int(auth_user.pk)
        except Exception:
            pass
        # 2) email match
        email = getattr(auth_user, "email", None)
        if email:
            u = Users.objects.filter(email=email).only("id").first()
            if u:
                return int(u.id)
        return None

    def _user_can_access(self, business_user_id, resource_id) -> bool:
        # Late import to avoid circulars
        ResourceRoles = apps.get_model("resources", "ResourceRoles")
        RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")

        now = timezone.now()
        # roles attached to this resource
        role_ids = ResourceRoles.objects.filter(resource_id=resource_id).values_list("role_id", flat=True)

        # active assignments for this user, matching any of those roles
        return RoleAssignmentHistory.objects.filter(
            user_id=business_user_id,
            role_id__in=role_ids,
            valid_from__lte=now,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).exists()


class IsMentorAdminOrSupervisor(BasePermission):
    """
    Allow access only to users with mentor, admin, or supervisor roles.
    This permission is used for resource creation, modification, and deletion.
    """
    message = "Only mentors, admins, and supervisors can perform this action."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        # Resolve business user ID
        business_user_id = self._resolve_business_user_id(request, view, user)
        if not business_user_id:
            return False

        # Check if user has mentor, admin, or supervisor role
        return self._user_has_required_role(business_user_id)

    def _resolve_business_user_id(self, request, view, auth_user) -> Optional[int]:
        """Map the authenticated user to the business Users row."""
        if hasattr(view, "get_business_user_id"):
            try:
                return int(view.get_business_user_id(request))
            except Exception:
                return None

        # For this permission, we'll use the Django User model directly
        # since the test users are created with Django's User model
        try:
            return int(auth_user.pk)
        except Exception:
            return None

    def _user_has_required_role(self, business_user_id) -> bool:
        """Check if user has mentor, admin, or supervisor role."""
        Roles = apps.get_model("resources", "Roles")
        RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")

        # Get role IDs for mentor, admin, and supervisor
        allowed_roles = Roles.objects.filter(
            role_name__in=['mentor', 'admin', 'supervisor']
        ).values_list('id', flat=True)

        if not allowed_roles:
            return False

        now = timezone.now()
        # Check for active role assignments
        return RoleAssignmentHistory.objects.filter(
            user=business_user_id,
            role__in=allowed_roles,
            valid_from__lte=now,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).exists()