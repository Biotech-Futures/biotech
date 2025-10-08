from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.groups.models import GroupMembers

class IsGroupMemberOrStaff(BasePermission):
    """Allow if user is staff or a member of the target group."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        gid = view.kwargs.get("group_pk")
        return GroupMembers.objects.filter(user=request.user, group_id=gid).exists()
    

class CanModerateMessage(BasePermission):
    """
    Allow delete if:
    - user is staff, OR
    - user is a mentor/admin in the message's group
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return GroupMembers.objects.filter(
            user=user,
            group=obj.group,
            role__in=["mentor", "admin"],
        ).exists()
