from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import RoleAssignmentHistory, Roles, Resources, ResourceAudience, ResourceType
from apps.users.models import User
from datetime import datetime, time, date
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


class ResourceUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']

class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = ['id', 'type_name', 'type_description']

class RoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="slug", read_only=True)

    class Meta:
        model = Roles
<<<<<<< Updated upstream
        fields = ["id", "slug", "role_name"]
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}

    def to_internal_value(self, data):
        if isinstance(data, dict) and "role_name" in data and "slug" not in data:
            data = {**data, "slug": data["role_name"]}
        return super().to_internal_value(data)

    def validate_slug(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("slug cannot be blank.")
        qs = Roles.objects.filter(slug__iexact=name)
=======
        fields = ['id', 'slug']

    def validate_slug(self, value: str) -> str:
        slug = (value or "").strip()
        if not slug:
            raise serializers.ValidationError("slug cannot be blank.")
        qs = Roles.objects.filter(slug__iexact=slug)
>>>>>>> Stashed changes
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A role with this slug already exists.")
<<<<<<< Updated upstream
        return name
=======
        return slug
>>>>>>> Stashed changes

class RoleAssignmentHistorySerializer(serializers.ModelSerializer):
    # Keep nested read-only shape for GETs:
    user = ResourceUserSerializer(read_only=True)
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

    @extend_schema_field(serializers.BooleanField())
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


class ResourceAudienceSerializer(serializers.ModelSerializer):
<<<<<<< Updated upstream
    role_name = serializers.CharField(source="role.slug", read_only=True)
    track_name = serializers.CharField(source="track.track_code", read_only=True)
=======
    role_slug = serializers.CharField(source="role.slug", read_only=True)
    track_code = serializers.CharField(source="track.track_code", read_only=True)
>>>>>>> Stashed changes

    class Meta:
        model = ResourceAudience
        fields = ["id", "role", "role_slug", "track", "track_code"]


class ResourceAudienceWriteSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False)
    track_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("role_id") and not attrs.get("track_id"):
            raise serializers.ValidationError("Each audience rule must include role_id or track_id.")
        return attrs

class ResourcesSerializer(serializers.ModelSerializer):
    uploader = ResourceUserSerializer(source='uploader_user_id', read_only=True)
    # Resource type field - read as nested object, write as ID
    resource_type_detail = ResourceTypeSerializer(source='resource_type', read_only=True)
    resource_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ResourceType.objects.all(),
        source='resource_type',
        write_only=True,
        required=False,
        allow_null=True,
        help_text="ID of the resource type"
    )
    # Role visibility fields
    visible_roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Roles.objects.all()),
        write_only=True,
        required=False,
        help_text="List of role IDs that can access this resource"
    )
    audiences = ResourceAudienceSerializer(many=True, read_only=True)
    audience_rules = ResourceAudienceWriteSerializer(many=True, write_only=True, required=False)
    
    class Meta:
        model = Resources
        fields = [
            'id',
            'resource_name',
            'resource_description',
            'resource_type_detail',
            'resource_type_id',
            'track',
            'visibility_scope',
            'upload_datetime',
            # 'uploader',  # read-only field for display
            # 'uploader_id',  # write-only field for input
            'uploader',  # read-only field for display (automatically set)
            'deleted_flag',
            'deleted_datetime',
            'visible_roles', ##Custom Field (to be used for appending ResourceRoles data)
            'role_ids', ##Custom Field (to be used for appending ResourceRoles data)
            'audiences',
            'audience_rules',
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

    @extend_schema_field(RoleSerializer(many=True))
    def get_visible_roles(self, obj):
        """Get the roles that can access this resource"""
        audiences = ResourceAudience.objects.filter(resource=obj, role__isnull=False).select_related('role')
        return RoleSerializer([aud.role for aud in audiences], many=True).data

    def _replace_audiences(self, resource, *, role_ids=None, audience_rules=None):
        if role_ids is None and audience_rules is None:
            return

        ResourceAudience.objects.filter(resource=resource).delete()

        if role_ids is not None:
            for role in role_ids:
                ResourceAudience.objects.create(resource=resource, role=role)

        if audience_rules is not None:
            for rule in audience_rules:
                ResourceAudience.objects.create(
                    resource=resource,
                    role_id=rule.get("role_id"),
                    track_id=rule.get("track_id"),
                )

    def create(self, validated_data):
        """Create resource and specify roles for visibility (ResourceRoles)"""
        role_ids = validated_data.pop('role_ids', [])         
        audience_rules = validated_data.pop("audience_rules", [])
        resource = super().create(validated_data)
        
        self._replace_audiences(resource, role_ids=role_ids, audience_rules=audience_rules)
        
        return resource

    def update(self, instance, validated_data):
        """Update resource and roles"""
        role_ids = validated_data.pop('role_ids', None)
        audience_rules = validated_data.pop("audience_rules", None)
        
        resource = super().update(instance, validated_data)
        
        self._replace_audiences(resource, role_ids=role_ids, audience_rules=audience_rules)
        
        return resource

class ResourceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list view"""
    uploader = ResourceUserSerializer(source='uploader_user_id', read_only=True)
    resource_type_detail = ResourceTypeSerializer(source='resource_type', read_only=True)
    visible_roles = serializers.SerializerMethodField()
    audiences = ResourceAudienceSerializer(many=True, read_only=True)

    class Meta:
        model = Resources
        fields = [
            'id',
            'resource_name',
            'resource_description',
            'resource_type_detail',
            'track',
            'visibility_scope',
            'upload_datetime',
            'uploader',
            'visible_roles',
            'audiences',
        ]
    
    @extend_schema_field(RoleSerializer(many=True))
    def get_visible_roles(self, obj):
        """Get the roles that can access this resource"""
        audiences = ResourceAudience.objects.filter(resource=obj, role__isnull=False).select_related('role')
        return RoleSerializer([aud.role for aud in audiences], many=True).data
