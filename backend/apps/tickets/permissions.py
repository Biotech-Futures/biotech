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

    Same two-step shape: not signed in, and signed in but not support-capable.
    Both answer 403 in this deployment. DRF only produces a 401 when an
    authentication class offers a ``WWW-Authenticate`` header, and the only one
    configured here is ``SessionAuthentication``, which does not. Written out
    because the comment this replaced said 401 for the first step, and a client
    branching on that code has a branch that never runs.
    """

    message = "You do not have support privileges."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return is_support(request.user)
