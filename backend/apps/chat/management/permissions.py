from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMembership
from apps.users.models import AdminScope
from apps.users.utils.roles import get_active_assignment


ROLE_ADMIN = "admin"

SELF_DELETE_WINDOW = timedelta(minutes=10)


def _has_active_role_name(user, allowed_names):
    rah = get_active_assignment(user)
    return bool(rah and rah.role and rah.role.role_name in allowed_names)


class IsGroupMemberOrAdmin(BasePermission):
    """
    For GET/POST: allow if user is admin, or a member of the group.
    (Mentors are covered by membership since they belong to specific groups.)
    """
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_staff or _has_active_role_name(u, {ROLE_ADMIN}):
            return True
        gid = view.kwargs.get("group_pk")
        return GroupMembership.objects.filter(
            user=u,
            group_id=gid,
            left_at__isnull=True,
        ).exists()


class CanModerateMessage(BasePermission):
    """
    For DELETE /chat/messages/{message_id}/:

    - **Sender (self-delete)**: allowed only within ``SELF_DELETE_WINDOW``
      (10 minutes) of the message's ``sent_at``.
    - **Global admin** — strictly an ``AdminScope`` row with
      ``is_global=True``. ``is_staff`` and ``is_superuser`` flags do **not**
      grant chat moderation on their own; an explicit scope row is required.
    - **Track admin** — an ``AdminScope`` row (``is_global=False``) whose
      ``track`` matches the message's group's track. Allowed only for
      messages in that track, no time limit.
    - **Everyone else** (including mentor / supervisor, the ``admin`` role
      assignment alone, and bare staff/superuser flags with no
      ``AdminScope`` row): denied.

    Note: this is intentionally stricter than ``apps.users.utils
    .admin_scope.can_admin_track``, which honors ``is_staff`` /
    ``is_superuser`` as global admin. Chat moderation always requires an
    ``AdminScope`` row.
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        print(
            f"[CanModerateMessage] v=adminscope-strict "
            f"user={getattr(u, 'email', None)} "
            f"is_staff={getattr(u, 'is_staff', None)} "
            f"is_superuser={getattr(u, 'is_superuser', None)} "
            f"msg_id={obj.id} sender_id={obj.sender_user_id} "
            f"track_id={obj.group.track_id}",
            flush=True,
        )
        if not u or not u.is_authenticated:
            print("[CanModerateMessage] -> deny (unauthenticated)", flush=True)
            return False

        if obj.sender_user_id == u.id:
            if timezone.now() <= obj.sent_at + SELF_DELETE_WINDOW:
                print("[CanModerateMessage] -> allow (sender within window)", flush=True)
                return True

        ok = AdminScope.objects.filter(
            Q(is_global=True) | Q(track_id=obj.group.track_id),
            user=u,
        ).exists()
        print(f"[CanModerateMessage] -> {'allow' if ok else 'deny'} (adminscope check)", flush=True)
        return ok
