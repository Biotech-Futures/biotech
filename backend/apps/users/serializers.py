from rest_framework import serializers
from .models import User, StudentProfile, MentorProfile
from apps.resources.models import RoleAssignmentHistory
from apps.groups.models import Tracks
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from zoneinfo import available_timezones


# Validate body payload
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
    YearLevel = serializers.CharField(max_length=255)
    Areaofinterest = serializers.CharField(max_length=255)

# Registration Wrapper
class UserRegisterRequestSerializer(serializers.Serializer):
    body = UserRegisterBodySerializer()

# Validate join permission
class JoinPermissionBodySerializer(serializers.Serializer):
    Email = serializers.EmailField()
    ResponseID = serializers.CharField(max_length=255)

# Join Permission Wrapper
class JoinPermissionRequestSerializer(serializers.Serializer):
    body = JoinPermissionBodySerializer()

class UserSerializer(serializers.ModelSerializer):
    current_role_id = serializers.SerializerMethodField()
    current_role_name = serializers.SerializerMethodField()

    #student
    pg_firstname = serializers.SerializerMethodField()
    pg_lastname = serializers.SerializerMethodField()
    year_lvl = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    join_perm = serializers.SerializerMethodField()

    #mentor
    ment_inst = serializers.SerializerMethodField()
    ment_reason = serializers.SerializerMethodField()
    ment_max_groups = serializers.SerializerMethodField()

    # Onboarding gate: tells the FE whether the user is still on their
    # invited/default-password state and must complete the password set/change
    # flow before they're allowed into the dashboard. See `get_must_change_password`.
    must_change_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "account_status", "track", "current_role_id", "current_role_name", "pg_firstname", "pg_lastname", "year_lvl", "school_name", "join_perm", "ment_inst", "ment_reason", "ment_max_groups", "must_change_password", "timezone"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance cache so serializing one user doesn't fire 10+ queries
        # for the same RoleAssignmentHistory / StudentProfile / MentorProfile.
        self._cache_assignment: dict[int, object] = {}
        self._cache_student: dict[int, object] = {}
        self._cache_mentor: dict[int, object] = {}

    def validate_timezone(self, value):
        if value not in available_timezones():
            raise serializers.ValidationError(f"Unknown IANA timezone: {value!r}")
        return value

    def _active_assignment(self, user):
        if user.id in self._cache_assignment:
            return self._cache_assignment[user.id]
        now = timezone.now()
        rah = (
            RoleAssignmentHistory.objects
            .select_related("role")
            .filter(user=user, valid_from__lte=now)
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
            .order_by("-valid_from")
            .first()
        )
        self._cache_assignment[user.id] = rah
        return rah

    def _student_profile(self, user):
        if user.id in self._cache_student:
            return self._cache_student[user.id]
        rah = self._active_assignment(user)
        profile = None
        if rah and rah.role_id == 4:
            profile = StudentProfile.objects.filter(user=user).first()
        self._cache_student[user.id] = profile
        return profile

    def _mentor_profile(self, user):
        if user.id in self._cache_mentor:
            return self._cache_mentor[user.id]
        rah = self._active_assignment(user)
        profile = None
        if rah and rah.role_id == 3:
            profile = MentorProfile.objects.filter(user=user).first()
        self._cache_mentor[user.id] = profile
        return profile

    # Annotation add to explicitly declare output type as drf-speculator cannot infer “unable to resolve type hint for..."
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_current_role_id(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None else rah.role_id

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_current_role_name(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None or rah.role is None else rah.role.role_name
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pg_firstname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_first_name
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pg_lastname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_last_name
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_year_lvl(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.year_lvl
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_school_name(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.school_name
    
    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_join_perm(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.has_join_permission
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_ment_inst(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.institution
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_ment_reason(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.mentor_reason
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ment_max_groups(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.max_group_count

    @extend_schema_field(serializers.BooleanField())
    def get_must_change_password(self, obj) -> bool:
        # Source of truth is Django's `has_usable_password()`. Users created via
        # the admin bulk-create / self-registration paths start with an unusable
        # password (they onboard via OTP / magic link), so this returns True
        # until they complete `AdminSetPasswordView`, `confirm_password_reset`,
        # or any other code path that calls `set_password(...)`. As soon as a
        # usable password exists this flips to False — exactly the contract the
        # FE asked for ("becomes false after they successfully update their
        # password"). This mirrors the signal already exposed to the admin
        # portal via `AdminPasswordStatusView.hasPassword` and so requires no
        # new schema / migration.
        return not obj.has_usable_password()


class UserStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["account_status"]


class BulkUserStatusSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    account_status = serializers.ChoiceField(choices=User.AccountStatus.choices)


class BulkUserTrackSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    track_id = serializers.PrimaryKeyRelatedField(queryset=Tracks.objects.all(), source="track")


class AdminOperationsSummarySerializer(serializers.Serializer):
    track_scope = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
    )
    active_users = serializers.IntegerField()
    invited_or_pending_users = serializers.IntegerField()
    suspended_or_deactivated_users = serializers.IntegerField()
    active_groups = serializers.IntegerField()
    groups_without_mentor = serializers.IntegerField()
    unassigned_match_recommendations = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
