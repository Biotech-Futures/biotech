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
