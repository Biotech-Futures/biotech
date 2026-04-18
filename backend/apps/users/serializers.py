from rest_framework import serializers
from .models import User, StudentProfile, MentorProfile
from apps.resources.models import RoleAssignmentHistory
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field


class UserRegisterBodySerializer(serializers.Serializer):
    Title = serializers.EmailField()
    FirstName = serializers.CharField(max_length=255)
    Surname = serializers.CharField(max_length=255)
    Country = serializers.CharField(max_length=255)
    Region = serializers.CharField(max_length=255, required=False, allow_blank=True)
    SupervisorEmail = serializers.EmailField()
    SupervisorFirstName = serializers.CharField(max_length=255)
    SupervisorSurname = serializers.CharField(max_length=255)
    GuardianEmail = serializers.EmailField()
    GuardianName = serializers.CharField(max_length=255)
    GuardianSurname = serializers.CharField(max_length=255)
    SchoolName = serializers.CharField(max_length=255)
    YearLevel = serializers.IntegerField()
    Areaofinterest = serializers.CharField(max_length=255)


class UserRegisterRequestSerializer(serializers.Serializer):
    body = UserRegisterBodySerializer()


class JoinPermissionBodySerializer(serializers.Serializer):
    Email = serializers.EmailField()
    ResponseID = serializers.CharField(max_length=255)


class JoinPermissionRequestSerializer(serializers.Serializer):
    body = JoinPermissionBodySerializer()


class UserSerializer(serializers.ModelSerializer):
    current_role_id = serializers.SerializerMethodField()
    current_role_slug = serializers.SerializerMethodField()

    # student
    year_level = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    join_permission_received = serializers.SerializerMethodField()

    # mentor
    ment_inst = serializers.SerializerMethodField()
    ment_max_groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "email", "is_active", "account_status",
            "track", "current_role_id", "current_role_slug",
            "year_level", "school_name", "join_permission_received",
            "ment_inst", "ment_max_groups",
        ]
        read_only_fields = ["id"]

    def _active_assignment(self, user):
        now = timezone.now()
        return (
            RoleAssignmentHistory.objects
            .select_related("role")
            .filter(user=user, valid_from__lte=now)
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
            .order_by("-valid_from")
            .first()
        )

    def _student_profile(self, user):
        rah = self._active_assignment(user)
        if rah and rah.role_id == 4:
            return StudentProfile.objects.filter(user=user).first()
        return None

    def _mentor_profile(self, user):
        rah = self._active_assignment(user)
        if rah and rah.role_id == 3:
            return MentorProfile.objects.filter(user=user).first()
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_current_role_id(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None else rah.role_id

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_current_role_slug(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None or rah.role is None else rah.role.slug
<<<<<<< Updated upstream
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pg_firstname(self, obj):
=======

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_year_level(self, obj):
>>>>>>> Stashed changes
        sp = self._student_profile(obj)
        return None if sp is None else sp.year_level

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_school_name(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.school_name

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_join_permission_received(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.join_permission_received
<<<<<<< Updated upstream
    
=======

>>>>>>> Stashed changes
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_ment_inst(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.institution

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ment_max_groups(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.max_group_count


class UserStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["is_active"]
