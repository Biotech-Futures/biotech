from pathlib import PurePosixPath
import re

from drf_spectacular.utils import extend_schema_field
from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.common.filenames import sanitize_upload_filename
from apps.common.upload_validation import is_truthy_flag, validate_uploaded_file
from apps.users.models import User

from .models import RoleAssignmentHistory, ResourceAudience, ResourceLabel, Resources, ResourceType, Roles
from .services.storage import (
    RESOURCE_FILE_SERVICE,
    is_external_storage_key,
    is_managed_storage_key,
    stored_resource_file,
    stored_resource_slides_file,
)
from datetime import date, datetime, time
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


class ResourceLabelSerializer(serializers.ModelSerializer):
    resource_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ResourceLabel
        fields = ['id', 'name', 'resource_count']


class ResourceAccessSerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    kind = serializers.CharField()
    storage_status = serializers.CharField()
    access_mode = serializers.CharField()
    access_url = serializers.URLField(allow_null=True)
    download_url = serializers.URLField(allow_null=True)
    external_url = serializers.URLField(allow_null=True)
    file_name = serializers.CharField(allow_null=True)
    file_mime_type = serializers.CharField(allow_null=True)
    file_size = serializers.IntegerField(allow_null=True)
    body_html = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    detail = serializers.CharField(allow_null=True)
    has_slides = serializers.BooleanField(required=False, default=False)
    slides_download_url = serializers.CharField(allow_null=True, required=False)


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
    user = ResourceUserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
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
        if "valid_from" in attrs:
            attrs["valid_from"] = self._coerce_dt(attrs["valid_from"])
        if "valid_to" in attrs:
            attrs["valid_to"] = self._coerce_dt(attrs["valid_to"])

        v_from = attrs.get("valid_from") or getattr(self.instance, "valid_from", None)
        v_to = attrs.get("valid_to", None)
        if v_from and v_to and v_to < v_from:
            raise serializers.ValidationError("valid_to cannot be before valid_from.")
        return attrs


class ResourceAudienceSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = ResourceAudience
        fields = ["id", "role", "role_name"]


class ResourceAudienceWriteSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("role_id"):
            raise serializers.ValidationError("Each audience rule must include role_id.")
        return attrs


class _ResourcePublicFieldsMixin(serializers.Serializer):
    uploader_name = serializers.SerializerMethodField()
    type_name = serializers.CharField(source='type.type_name', read_only=True, allow_null=True)
    file_name = serializers.SerializerMethodField()
    access_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    storage_status = serializers.SerializerMethodField()
    labels = ResourceLabelSerializer(many=True, read_only=True)
    has_slides = serializers.SerializerMethodField()
    slides_download_url = serializers.SerializerMethodField()

    def get_uploader_name(self, obj):
        if obj.uploaded_by_id is None:
            return None
        return obj.uploaded_by.get_full_name().strip() or obj.uploaded_by.email

    def get_file_name(self, obj):
        if obj.storage_key:
            raw_name = PurePosixPath(obj.storage_key).name
            stripped_name = re.sub(r"^\d+-\d+-", "", raw_name)
            return sanitize_upload_filename(stripped_name or raw_name)
        return obj.name

    def _build_route_url(self, obj, route_name):
        request = self.context.get("request")
        return reverse(route_name, kwargs={"pk": obj.pk}, request=request)

    def get_access_url(self, obj):
        if obj.storage_key:
            return self._build_route_url(obj, "resource-files-access")
        return None

    def get_download_url(self, obj):
        if obj.kind == Resources.ResourceKind.FILE and obj.storage_key:
            return self._build_route_url(obj, "resource-files-download")
        return None

    def get_has_slides(self, obj):
        return bool(obj.slides_storage_key)

    def get_slides_download_url(self, obj):
        if obj.slides_storage_key:
            url = self._build_route_url(obj, "resource-files-download")
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}field=slides"
        return None

    def get_storage_status(self, obj):
        if not obj.storage_key:
            return "unavailable"
        if str(obj.storage_key).startswith(("http://", "https://")):
            return "external_url"
        return "managed_key"


class ResourcesSerializer(_ResourcePublicFieldsMixin, serializers.ModelSerializer):
    uploader = ResourceUserSerializer(source='uploaded_by', read_only=True)
    resource_type_detail = ResourceTypeSerializer(source='type', read_only=True)
    type_id = serializers.PrimaryKeyRelatedField(
        queryset=ResourceType.objects.all(),
        source='type',
        write_only=True,
        required=False,
        allow_null=True,
        help_text="ID of the resource type"
    )
    resource_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ResourceType.objects.all(),
        source='type',
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Backward-compatible alias for type_id"
    )
    visible_roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Roles.objects.all()),
        write_only=True,
        required=False,
        help_text="List of role IDs that can access this resource"
    )
    uploaded_file = serializers.FileField(write_only=True, required=False, allow_null=True)
    slides_file = serializers.FileField(write_only=True, required=False, allow_null=True)
    audiences = ResourceAudienceSerializer(many=True, read_only=True)
    audience_rules = ResourceAudienceWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Resources
        fields = [
            'id',
            'name',
            'description',
            'resource_type_detail',
            'type_name',
            'type_id',
            'resource_type_id',
            'kind',
            'file_mime_type',
            'file_size',
            'storage_key',
            'uploaded_file',
            'slides_mime_type',
            'slides_file_size',
            'slides_storage_key',
            'slides_file',
            'has_slides',
            'slides_download_url',
            'group',
            'visibility_scope',
            'uploaded_at',
            'uploader',
            'uploader_name',
            'deleted_at',
            'file_name',
            'access_url',
            'download_url',
            'storage_status',
            'visible_roles',
            'role_ids',
            'audiences',
            'audience_rules',
        ]
        read_only_fields = ['id', 'uploaded_at', 'deleted_at']

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Resource description cannot be empty.")
        return value.strip()

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Resource name cannot be empty.")

        cleaned_name = value.strip()
        kind = (
            self.initial_data.get("kind")
            if hasattr(self, "initial_data") and isinstance(self.initial_data, dict)
            else None
        ) or getattr(self.instance, "kind", Resources.ResourceKind.FILE)
        if kind == Resources.ResourceKind.ATTACHMENT:
            return cleaned_name

        existing_resources = Resources.objects.filter(
            name__iexact=cleaned_name,
            deleted_at__isnull=True
        ).exclude(kind=Resources.ResourceKind.ATTACHMENT)
        if self.instance:
            existing_resources = existing_resources.exclude(id=self.instance.id)
        if existing_resources.exists():
            raise serializers.ValidationError(
                f"A resource with the name '{cleaned_name}' already exists. Please choose a different name."
            )
        return cleaned_name

    def validate_role_ids(self, value):
        if value is not None and len(value) == 0:
            raise serializers.ValidationError("At least one role must be specified for visibility.")
        return value

    def validate_uploaded_file(self, value):
        return validate_uploaded_file(
            value,
            max_size=settings.RESOURCE_FILE_MAX_UPLOAD_SIZE,
            allowed_extensions=settings.RESOURCE_FILE_ALLOWED_EXTENSIONS,
            allowed_mime_types=settings.RESOURCE_FILE_ALLOWED_MIME_TYPES,
            field_label="Resource file",
            # Not a model field: the uploader's "I understand this file is
            # large" confirmation, sent alongside the file.
            acknowledged_oversized=is_truthy_flag(
                self.initial_data.get("acknowledged_oversized")
            ),
        )

    def validate_slides_file(self, value):
        if value is None:
            return value
        return validate_uploaded_file(
            value,
            max_size=settings.RESOURCE_FILE_MAX_UPLOAD_SIZE,
            allowed_extensions=("pdf",),
            allowed_mime_types=("application/pdf",),
            field_label="Slides file",
            acknowledged_oversized=is_truthy_flag(
                self.initial_data.get("acknowledged_oversized")
            ),
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        uploaded_file = attrs.get("uploaded_file")
        kind = attrs.get("kind", getattr(self.instance, "kind", Resources.ResourceKind.FILE))
        storage_key = attrs.get("storage_key", getattr(self.instance, "storage_key", None))

        target_type = attrs.get("type", getattr(self.instance, "type", None))
        is_recorded_session = bool(target_type and target_type.type_name == "Recorded Session")

        if is_recorded_session and kind != Resources.ResourceKind.FILE:
            raise serializers.ValidationError(
                {"kind": "Recorded Session resources must be file resources."}
            )

        slides_file = attrs.get("slides_file")
        if slides_file is not None and not is_recorded_session:
            raise serializers.ValidationError(
                {"slides_file": "Slides files are only supported for Recorded Session resources."}
            )

        if uploaded_file and (kind not in [Resources.ResourceKind.FILE, Resources.ResourceKind.ATTACHMENT]):
            raise serializers.ValidationError({"uploaded_file": "Only file and attachment resources can accept uploaded files."})

        if kind == Resources.ResourceKind.PAGE:
            if uploaded_file is not None:
                raise serializers.ValidationError({"uploaded_file": "Page resources cannot accept uploaded files."})
            if not is_external_storage_key(storage_key):
                raise serializers.ValidationError(
                    {"storage_key": "Page resources require an external http(s) storage_key URL."}
                )

        self._validate_role_visibility(attrs)
        return attrs

    def _validate_role_visibility(self, attrs):
        # Resources are role-scoped (or group/scoped); "public" can no longer
        # be written. Legacy public rows are tolerated until something sets it.
        if attrs.get("visibility_scope") == Resources.VisibilityScope.PUBLIC:
            raise serializers.ValidationError(
                {"visibility_scope": "Public visibility is no longer supported. Select the roles that can view this resource."}
            )

        scope = attrs.get(
            "visibility_scope",
            getattr(self.instance, "visibility_scope", Resources.VisibilityScope.ROLE),
        )
        if scope != Resources.VisibilityScope.ROLE:
            return

        role_ids = attrs.get("role_ids")
        audience_rules = attrs.get("audience_rules")
        roles_sent = role_ids is not None or audience_rules is not None
        if self.instance is not None and not roles_sent and "visibility_scope" not in attrs:
            # An update that doesn't touch visibility (a rename, a type change)
            # isn't blocked; this matches the admin update_resource check.
            return
        if roles_sent:
            has_roles = bool(role_ids) or bool(audience_rules)
        else:
            # Omitting role_ids used to skip the check entirely; on update the
            # resource's existing audience has to qualify instead.
            has_roles = self.instance is not None and self.instance.audiences.exists()
        if not has_roles:
            raise serializers.ValidationError(
                {"role_ids": "At least one role must be specified for visibility."}
            )

    @extend_schema_field(RoleSerializer(many=True))
    def get_visible_roles(self, obj):
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
                )

    def create(self, validated_data):
        role_ids = validated_data.pop('role_ids', [])
        audience_rules = validated_data.pop("audience_rules", [])
        uploaded_file = validated_data.pop("uploaded_file", None)
        slides_file = validated_data.pop("slides_file", None)

        def _do_create(v_data):
            v_data["kind"] = v_data.get("kind", Resources.ResourceKind.FILE)
            resource = super(ResourcesSerializer, self).create(v_data)
            self._replace_audiences(resource, role_ids=role_ids, audience_rules=audience_rules)
            return resource

        if uploaded_file is not None and slides_file is not None:
            with stored_resource_file(uploaded_file) as file_data:
                validated_data.update(file_data)
                with stored_resource_slides_file(slides_file) as slides_data:
                    validated_data["slides_storage_key"] = slides_data["storage_key"]
                    validated_data["slides_mime_type"] = slides_data["slides_mime_type"]
                    validated_data["slides_file_size"] = slides_data["slides_file_size"]
                    return _do_create(validated_data)
        elif uploaded_file is not None:
            with stored_resource_file(uploaded_file) as file_data:
                validated_data.update(file_data)
                return _do_create(validated_data)
        elif slides_file is not None:
            with stored_resource_slides_file(slides_file) as slides_data:
                validated_data["slides_storage_key"] = slides_data["storage_key"]
                validated_data["slides_mime_type"] = slides_data["slides_mime_type"]
                validated_data["slides_file_size"] = slides_data["slides_file_size"]
                return _do_create(validated_data)
        else:
            return _do_create(validated_data)

    def update(self, instance, validated_data):
        role_ids = validated_data.pop('role_ids', None)
        audience_rules = validated_data.pop("audience_rules", None)
        uploaded_file = validated_data.pop("uploaded_file", None)
        slides_file = validated_data.pop("slides_file", None)
        old_storage_key = instance.storage_key
        incoming_storage_key = validated_data.get("storage_key", instance.storage_key)
        old_slides_storage_key = instance.slides_storage_key
        incoming_slides_storage_key = validated_data.get("slides_storage_key", instance.slides_storage_key)

        def _do_update(inst, v_data):
            res = super(ResourcesSerializer, self).update(inst, v_data)
            self._replace_audiences(res, role_ids=role_ids, audience_rules=audience_rules)
            if (
                "storage_key" in v_data
                and old_storage_key != incoming_storage_key
                and is_managed_storage_key(old_storage_key)
            ):
                RESOURCE_FILE_SERVICE.delete(old_storage_key)
            if (
                "slides_storage_key" in v_data
                and old_slides_storage_key != incoming_slides_storage_key
                and is_managed_storage_key(old_slides_storage_key)
            ):
                RESOURCE_FILE_SERVICE.delete(old_slides_storage_key)
            return res

        if uploaded_file is not None and slides_file is not None:
            with stored_resource_file(uploaded_file) as file_data:
                validated_data.update(file_data)
                with stored_resource_slides_file(slides_file) as slides_data:
                    validated_data["slides_storage_key"] = slides_data["storage_key"]
                    validated_data["slides_mime_type"] = slides_data["slides_mime_type"]
                    validated_data["slides_file_size"] = slides_data["slides_file_size"]
                    resource = _do_update(instance, validated_data)
        elif uploaded_file is not None:
            with stored_resource_file(uploaded_file) as file_data:
                validated_data.update(file_data)
                resource = _do_update(instance, validated_data)
        elif slides_file is not None:
            with stored_resource_slides_file(slides_file) as slides_data:
                validated_data["slides_storage_key"] = slides_data["storage_key"]
                validated_data["slides_mime_type"] = slides_data["slides_mime_type"]
                validated_data["slides_file_size"] = slides_data["slides_file_size"]
                resource = _do_update(instance, validated_data)
        else:
            resource = _do_update(instance, validated_data)

        if old_storage_key != resource.storage_key and is_managed_storage_key(old_storage_key):
            RESOURCE_FILE_SERVICE.delete(old_storage_key)
        if old_slides_storage_key != resource.slides_storage_key and is_managed_storage_key(old_slides_storage_key):
            RESOURCE_FILE_SERVICE.delete(old_slides_storage_key)

        return resource


class _BaseResourcePublicSerializer(_ResourcePublicFieldsMixin, serializers.ModelSerializer):
    pass


class ResourcePublicListSerializer(_BaseResourcePublicSerializer):
    class Meta:
        model = Resources
        fields = [
            'id',
            'name',
            'description',
            'type_name',
            'kind',
            'file_mime_type',
            'file_size',
            'uploaded_at',
            'uploader_name',
            'file_name',
            'access_url',
            'download_url',
            'storage_status',
            'labels',
            'has_slides',
            'slides_mime_type',
            'slides_file_size',
            'slides_download_url',
        ]


class ResourcePublicDetailSerializer(_BaseResourcePublicSerializer):
    class Meta:
        model = Resources
        fields = [
            'id',
            'name',
            'description',
            'type_name',
            'kind',
            'file_mime_type',
            'file_size',
            'uploaded_at',
            'uploader_name',
            'file_name',
            'access_url',
            'download_url',
            'storage_status',
            'labels',
            'has_slides',
            'slides_mime_type',
            'slides_file_size',
            'slides_download_url',
        ]
