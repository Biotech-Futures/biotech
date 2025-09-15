from rest_framework import serializers
from django.utils import timezone
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

class RoleAssignmentCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True)
    role_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = RoleAssignmentHistory
        fields = [
            'user_id',
            'role_id',
            'valid_from',
            'valid_to'
        ]

    def validate_user_id(self, value):
        """Validate that the user exists"""
        try:
            Users.objects.get(id=value)
        except Users.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        return value

    def validate_role_id(self, value):
        """Validate that the role exists"""
        try:
            Roles.objects.get(id=value)
        except Roles.DoesNotExist:
            raise serializers.ValidationError("Role does not exist")
        return value

    def validate(self, data):
        """Validate date logic"""
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')

        if valid_from and valid_from < timezone.now():
            raise serializers.ValidationError(
                "valid_from cannot be in the past"
            )

        if valid_to and valid_from and valid_to <= valid_from:
            raise serializers.ValidationError(
                "valid_to must be after valid_from"
            )

        return data

    def create(self, validated_data):
        """Create role assignment"""
        user = Users.objects.get(id=validated_data.pop('user_id'))
        role = Roles.objects.get(id=validated_data.pop('role_id'))

        return RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            **validated_data
        )