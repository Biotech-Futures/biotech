from rest_framework import serializers, generics, permissions, status
from .models import User, StudentProfile, MentorProfile
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.users.utils.roles import get_active_assignment
from django.utils import timezone

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
    ment_bg = serializers.SerializerMethodField()
    ment_inst = serializers.SerializerMethodField()
    ment_reason = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "status", "track", "state", "current_role_id", "current_role_name", "pg_firstname", "pg_lastname", "year_lvl", "school_name", "join_perm", "ment_bg", "ment_inst", "ment_reason"]
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
        # return get_active_assignment
    
        
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

    def get_current_role_id(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None else rah.role_id

    def get_current_role_name(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None or rah.role is None else rah.role.role_name
    
    def get_pg_firstname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_first_name
    
    def get_pg_lastname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_last_name
    
    def get_year_lvl(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.year_lvl
    
    def get_school_name(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.school_name
    
    def get_join_perm(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.has_join_permission
    
    def get_ment_bg(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.background
    
    def get_ment_inst(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.institution
    
    def get_ment_reason(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.mentor_reason

class UserStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["status"]