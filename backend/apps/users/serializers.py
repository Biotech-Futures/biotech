from rest_framework import serializers
from .models import AreasOfInterest, User, StudentProfile, MentorProfile, UserInterest
from apps.resources.models import RoleAssignmentHistory
from apps.groups.models import Tracks
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field 


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
    interests = serializers.SerializerMethodField()

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

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "account_status",
            "track",
            "contact_method",
            "availability",
            "interests",
            "current_role_id",
            "current_role_name",
            "pg_firstname",
            "pg_lastname",
            "year_lvl",
            "school_name",
            "join_perm",
            "ment_inst",
            "ment_reason",
            "ment_max_groups",
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
            return (
                StudentProfile.objects
                .filter(user=user)
                .first()
            )
        elif rah and rah.role_id == 3:
            return None
        return None
        
    def _mentor_profile(self, user):
        rah = self._active_assignment(user)
        if rah and rah.role_id == 4:
            return None
        elif rah and rah.role_id == 3:
            return(
                MentorProfile.objects
                .filter(user=user)
                .first()
            )
        return None

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

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_interests(self, obj):
        return list(
            UserInterest.objects
            .filter(user=obj)
            .select_related("interest")
            .order_by("interest__interest_desc", "id")
            .values_list("interest__interest_desc", flat=True)
        )


class MeProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    contact_method = serializers.ChoiceField(choices=User.ContactMethod.choices, required=False)
    availability = serializers.CharField(required=False, allow_blank=True)
    interests = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable profile field must be supplied.")
        return attrs

    def validate_interests(self, value):
        normalized = []
        seen = set()
        for interest in value:
            cleaned = str(interest).strip()
            if not cleaned:
                raise serializers.ValidationError("Interest values must not be blank.")
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned)
        return normalized

class UserStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["account_status"]


class AdminUserSerializer(UserSerializer):
    track_name = serializers.CharField(source="track.track_name", read_only=True, allow_null=True)
    state_id = serializers.IntegerField(source="track.state_id", read_only=True, allow_null=True)
    state_name = serializers.CharField(source="track.state.state_name", read_only=True, allow_null=True)

    class Meta(UserSerializer.Meta):
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "account_status",
            "is_active",
            "is_staff",
            "is_superuser",
            "track",
            "track_name",
            "state_id",
            "state_name",
            "current_role_id",
            "current_role_name",
            "invited_at",
            "activated_at",
        ]


class AdminUserUpdateSerializer(serializers.Serializer):
    account_status = serializers.ChoiceField(choices=User.AccountStatus.choices, required=False)
    track_id = serializers.PrimaryKeyRelatedField(
        queryset=Tracks.objects.all(),
        source="track",
        required=False,
    )
    role_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be supplied.")
        return attrs


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
