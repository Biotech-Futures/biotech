from rest_framework import serializers
from .models import RoleAssignmentHistory, Roles
from apps.users.models import Users

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ['id', 'first_name', 'last_name', 'email']

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roles
        fields = ['id', 'role_name']

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