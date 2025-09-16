from rest_framework import serializers, generics, permissions, status
from apps.users.models import User
from apps.resources.models import Roles, RoleAssignmentHistory
from django.utils import timezone

class UserSerializer(serializers.ModelSerializer):
    current_role_id = serializers.SerializerMethodField()
    current_role_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "status", "track", "state", "current_role_id", "current_role_name"]
        read_only_fields = ["id"]

    def _active_assignment(self, user):
        now = timezone.now()
        return (
            RoleAssignmentHistory.objects
            .select_related("role")
            .filter(user=user, valid_from__lte=now, valid_to__gte=now)
            .order_by("-valid_from")
            .first()
        )

    def get_current_role_id(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None else rah.role_id

    def get_current_role_name(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None or rah.role is None else rah.role.role_name

class UserStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["status"]

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roles
        fields = ["id", "role_name"]

class RoleAssignmentHistorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)

    class Meta:
        model = RoleAssignmentHistory
        fields = [
            'id',
            'user',
            'role',
            'valid_from',
            'valid_to'
        ]