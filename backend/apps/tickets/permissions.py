from rest_framework.permissions import BasePermission

from apps.common.rbac import is_admin

from .models import SupportScope


def is_support(user) -> bool:
    """The one place that answers "can this person work the support queue?".

    Every admin is support-capable; not every support agent is an admin
    (DEC-001, from the client's own annotation on p47). That OR must not be
    written out anywhere else — a second copy is how the two halves drift.

    The authentication guard is load-bearing, not defensive noise: querying
    with an ``AnonymousUser`` instance raises ``TypeError`` and would surface
    as a 500 rather than a 403 (DEC-019 B3).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if SupportScope.objects.filter(user=user).exists():
        return True
    return is_admin(user)


class IsSupportScoped(BasePermission):
    """Mirror of ``apps.admin.permissions.IsAdminScoped`` for the support side.

    Same two-step shape: not signed in -> 401, signed in but not support-capable
    -> 403.
    """

    message = "You do not have support privileges."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return is_support(request.user)
