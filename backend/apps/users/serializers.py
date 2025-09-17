from rest_framework import serializers, generics, permissions, status
from .models import User, StudentProfile, MentorProfile, SupervisorProfile, Background, AreasOfInterest
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
        fields = ["role_id", "role_name"]

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

class UnifiedRegisterSerializer(serializers.Serializer):
    # Common user fields
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.ChoiceField(choices=["student", "mentor", "supervisor"])

    # Student-specific
    pg_first_name = serializers.CharField(required=False, allow_blank=True)
    pg_last_name = serializers.CharField(required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    school_name = serializers.CharField(required=False, allow_blank=True)
    year_lvl = serializers.CharField(required=False, allow_blank=True)
    area_of_interest = serializers.CharField(required=False, allow_blank=True)

    # Mentor-specific
    background_id = serializers.PrimaryKeyRelatedField(
        queryset=Background.objects.all(),
        required=False,
        source="background"
    )
    institution = serializers.CharField(required=False, allow_blank=True)
    mentor_reason = serializers.CharField(required=False, allow_blank=True)
    max_grp_cnt = serializers.IntegerField(required=False)

    # Supervisor-specific
    supervisor_school_name = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        role = validated_data.pop("role")
        user = User.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"]
        )
        user.set_unusable_password()
        user.save()

        if role == "student":
            StudentProfile.objects.create(
                user=user,
                pg_first_name=validated_data.get("pg_first_name", ""),
                pg_last_name=validated_data.get("pg_last_name", ""),
                parent_guardian_flag=bool(validated_data.get("guardian_email")),
                school_name=validated_data.get("school_name", ""),
                year_lvl=validated_data.get("year_lvl", ""),
                has_join_permission=False
            )

        elif role == "mentor":
            MentorProfile.objects.create(
                user=user,
                background=validated_data.get("background"),
                institution=validated_data.get("institution", ""),
                mentor_reason=validated_data.get("mentor_reason", ""),
                max_grp_cnt=validated_data.get("max_grp_cnt", 0)
            )

        elif role == "supervisor":
            SupervisorProfile.objects.create(
                user=user,
                school_name=validated_data.get("supervisor_school_name", "")
            )

        return user