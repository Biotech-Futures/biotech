from rest_framework import serializers
from .models import RoleAssignmentHistory, Roles, Resources, ResourceRoles
from apps.users.models import User
from datetime import datetime, time, date
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


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
    # Keep nested read-only shape for GETs:
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)

    # Accept role updates via role_id on PATCH:
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Roles.objects.all(),
        source="role",
        write_only=True,
        required=False,
    )

    is_active = serializers.SerializerMethodField()

    class Meta:
        model = RoleAssignmentHistory
        fields = ["id", "user", "role", "role_id", "valid_from", "valid_to", "is_active"]

    def get_is_active(self, obj):
        return obj.valid_to is None or obj.valid_to >= timezone.now()

    # ---- helpers to accept both YYYY-MM-DD and datetimes, and make them TZ-aware
    def _coerce_dt(self, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime.combine(value, time.min)
        elif isinstance(value, str):
            dt = parse_datetime(value)
            if dt is None:
                d = parse_date(value)
                if d:
                    dt = datetime.combine(d, time.min)
            if dt is None:
                raise serializers.ValidationError("Invalid datetime/date format.")
        else:
            return value

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt

    def validate(self, attrs):
        # Only for fields being updated in PATCH
        if "valid_from" in attrs:
            attrs["valid_from"] = self._coerce_dt(attrs["valid_from"])
        if "valid_to" in attrs:
            attrs["valid_to"] = self._coerce_dt(attrs["valid_to"])

        v_from = attrs.get("valid_from") or getattr(self.instance, "valid_from", None)
        v_to   = attrs.get("valid_to", None)
        if v_from and v_to and v_to < v_from:
            raise serializers.ValidationError("valid_to cannot be before valid_from.")
        return attrs

class ResourcesSerializer(serializers.ModelSerializer):
    uploader = UserSerializer(source='uploader_user_id', read_only=True)

    # uploader_id is automatically set to the authenticated user - no need for input field    # Users can only see input: user ID
    # uploader_id = serializers.PrimaryKeyRelatedField(
    #     queryset=User.objects.all(),
    #     source='uploader_user_id',
    #     write_only=True,
    #     required=True #Set to Required field
    # )
    
    # Role visibility fields
    visible_roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Roles.objects.all()),
        write_only=True, 
        required=False,
        help_text="List of role IDs that can access this resource"
    )
    
    class Meta:
        model = Resources
        fields = [
            'id', 
            'resource_name', 
            'resource_description', 
            'upload_datetime', 
            # 'uploader',  # read-only field for display
            # 'uploader_id',  # write-only field for input
            'uploader',  # read-only field for display (automatically set)
            'deleted_flag', 
            'deleted_datetime',
            'visible_roles', ##Custom Field (to be used for appending ResourceRoles data) 
            'role_ids' ##Custom Field (to be used for appending ResourceRoles data) 
        ]
        read_only_fields = ['id', 'upload_datetime', 'deleted_datetime']

    def validate_resource_description(self, value):
        """Ensure description is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Resource description cannot be empty.")
        return value.strip()

    def validate_resource_name(self, value):
        """Clean and validate resource name - cannot be null or empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Resource name cannot be empty.")
        
        cleaned_name = value.strip()
        
        # Check for duplicate resource names (excluding deleted resources)
        existing_resources = Resources.objects.filter(
            resource_name__iexact=cleaned_name,
            deleted_flag=False
        )
        
        # If updating, exclude current instance from duplicate check
        if self.instance:
            existing_resources = existing_resources.exclude(id=self.instance.id)
        
        if existing_resources.exists():
            raise serializers.ValidationError(
                f"A resource with the name '{cleaned_name}' already exists. Please choose a different name."
            )
        
        return cleaned_name

    def validate_role_ids(self, value):
        """Validate that role_ids are not empty if provided"""
        if value is not None and len(value) == 0:
            raise serializers.ValidationError("At least one role must be specified for visibility.")
        return value
    
    # uploader_id validation removed - it's automatically set to authenticated user
        # def validate_uploader_id(self, value):
        # """Validate that uploader_id is provided and not empty"""
        # if value is None:
        #     raise serializers.ValidationError("Uploader ID is required and cannot be empty.")
        # return value
    def get_visible_roles(self, obj):
        """Get the roles that can access this resource"""
        from .models import ResourceRoles
        resource_roles = ResourceRoles.objects.filter(resource=obj).select_related('role')
        return RoleSerializer([rr.role for rr in resource_roles], many=True).data

    def create(self, validated_data):
        """Create resource and specify roles for visibility (ResourceRoles)"""
        role_ids = validated_data.pop('role_ids', []) 
        
        # uploader_user_id is automatically set by perform_create in the viewset        # Set uploader to current user if not specified
        # if 'uploader_user_id' not in validated_data:
        #     validated_data['uploader_user_id'] = self.context['request'].user
        
        resource = super().create(validated_data)
        
        # Assign roles to resource (ResourceRoles)
        for role_id in role_ids:
            ResourceRoles.objects.create(resource=resource, role=role_id)
        
        return resource

    def update(self, instance, validated_data):
        """Update resource and roles"""
        role_ids = validated_data.pop('role_ids', None)
        
        resource = super().update(instance, validated_data)
        
        # Update roles if provided
        if role_ids is not None:
            # Remove existing role assignments
            ResourceRoles.objects.filter(resource=resource).delete()
            # Add new role assignments
            for role_id in role_ids:
                ResourceRoles.objects.create(resource=resource, role=role_id)
        
        return resource

class ResourceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list view"""
    uploader = UserSerializer(source='uploader_user_id', read_only=True)
    visible_roles = RoleSerializer(source='resourceroles_set__role', many=True, read_only=True)
    
    class Meta:
        model = Resources
        fields = [
            'id', 
            'resource_name', 
            'resource_description', 
            'upload_datetime', 
            'uploader',
            'visible_roles'
        ]
