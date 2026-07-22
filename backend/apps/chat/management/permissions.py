from django.conf import settings
from rest_framework.permissions import BasePermission

from apps.chat.rbac import can_access_chat_group, can_manage_chat_message
from apps.groups.models import Groups


class HasParentalConsentToPost(BasePermission):
    """Block a student from posting until parental join-permission is recorded.

    No-op unless ``settings.ENFORCE_JOIN_PERMISSION`` is enabled. The consent
    flag is populated by the external join-permission webhook, so enforcement is
    deploy-gated — turning it on before that data is backfilled would lock every
    student out of chat. Non-students (no StudentProfile) are unaffected.
    """

    message = "Parental join permission must be recorded before you can post."

    def has_permission(self, request, view):
        if not getattr(settings, "ENFORCE_JOIN_PERMISSION", False):
            return True
        from apps.users.models import StudentProfile
        sp = (
            StudentProfile.objects
            .filter(user=request.user)
            .only("has_join_permission")
            .first()
        )
        return sp is None or sp.has_join_permission


class IsGroupMemberOrAdmin(BasePermission):
    """Read / post: caller is an active member of the target group, or an admin.

    Delegates to the shared RBAC helper so REST, download, and websocket
    access stay aligned.
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        gid = view.kwargs.get("group_pk")
        # A deleted group no longer grants chat access through membership or admin scope.
        group = Groups.objects.only("id").filter(
            pk=gid,
            deleted_at__isnull=True,
        ).first()
        return can_access_chat_group(u, group)


class CanModerateMessage(BasePermission):
    """Delete a chat message.

    Allowed iff the caller is the sender within the self-action window,
    or an admin.
    """

    def has_object_permission(self, request, view, obj):
        return can_manage_chat_message(getattr(request, "user", None), obj)


class CanEditMessage(BasePermission):
    """Edit a chat message. Same rule as CanModerateMessage — sender
    within the self-action window, or an admin. Kept as a separate class
    so views wire intent explicitly.
    """

    def has_object_permission(self, request, view, obj):
        return can_manage_chat_message(getattr(request, "user", None), obj)
