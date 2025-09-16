from rest_framework import serializers
from .models import RoleAssignmentHistory, Roles
from apps.users.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roles
        fields = ['id', 'role_name']

    def validate_role_name(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("role_name cannot be blank.")
        qs = Roles.objects.filter(role_name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A role with this name already exists.")
        return name

class RoleAssignmentHistorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = RoleAssignmentHistory
        fields = [
            'id',
            'user',
            'role',
            'valid_from',
            'valid_to',
            'is_active'
        ]

    def get_is_active(self, obj):
        """Check if the role assignment is currently active"""
        return obj.valid_to is None