from rest_framework import serializers
from .models import RoleAssignmentHistory, Roles, Resources, ResourceRoles, ResourceType
from apps.users.models import User
from datetime import datetime, time, date, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.conf import settings
from django.core.files.base import ContentFile # Added for ContentFile handling
import mimetypes # Added for more robust content type detection


# ===== FILE TYPE VALIDATION SYSTEM =====
# Define allowed file extensions for each resource type
ALLOWED_FILE_TYPES = {
    'document': {
        'extensions': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
        'content_types': [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/rtf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ],
        'description': 'Documents: PDF, Word, Excel, PowerPoint, Text files'
    },
    'guide': {
        'extensions': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
        'content_types': [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/rtf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ],
        'description': 'Guides: PDF, Word, Excel, PowerPoint, Text files'
    },
    'template': {
        'extensions': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
        'content_types': [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/rtf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ],
        'description': 'Templates: PDF, Word, Excel, PowerPoint, Text files'
    },
    'image': {
        'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'],
        'content_types': [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/svg+xml',
            'image/webp',
            'image/tiff'
        ],
        'description': 'Images: JPG, PNG, GIF, BMP, SVG, WebP, TIFF'
    },
    'video': {
        'extensions': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
        'content_types': [
            'video/mp4',
            'video/x-msvideo',
            'video/quicktime',
            'video/x-ms-wmv',
            'video/x-flv',
            'video/webm',
            'video/x-matroska'
        ],
        'description': 'Videos: MP4, AVI, MOV, WMV, FLV, WebM, MKV'
    }
}


def validate_file_type_for_resource_type(file, resource_type_name):
    """
    Validate that the uploaded file type matches the specified resource type.
    
    Args:
        file: The uploaded file object
        resource_type_name: The name of the resource type (e.g., 'document', 'image')
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file or not file.name:
        return False, "No file provided"
    
    if resource_type_name not in ALLOWED_FILE_TYPES:
        return False, f"Unknown resource type: {resource_type_name}"
    
    # Get file extension
    file_extension = '.' + file.name.lower().split('.')[-1] if '.' in file.name else ''
    
    # Get content type
    content_type = getattr(file, 'content_type', None)
    if not content_type:
        # Try to detect from filename
        content_type, _ = mimetypes.guess_type(file.name)
    
    allowed_types = ALLOWED_FILE_TYPES[resource_type_name]
    
    # Check if extension is allowed
    if file_extension not in allowed_types['extensions']:
        return False, f"File extension '{file_extension}' is not allowed for resource type '{resource_type_name}'. Allowed extensions: {', '.join(allowed_types['extensions'])}"
    
    # Check if content type is allowed (if available)
    if content_type and content_type not in allowed_types['content_types']:
        return False, f"File content type '{content_type}' is not allowed for resource type '{resource_type_name}'. Allowed content types: {', '.join(allowed_types['content_types'])}"
    
    return True, None


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']

class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = ['id', 'type_name', 'type_description']

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
    uploader_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        help_text="ID of the user who uploaded this resource"
    )
    # Resource type field - read as nested object, write as ID
    resource_type_detail = ResourceTypeSerializer(source='resource_type', read_only=True)
    resource_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ResourceType.objects.all(),
        source='resource_type',
        write_only=True,
        required=True,  # Must be explicitly specified
        allow_null=False,
        help_text="ID of the resource type (REQUIRED - must be explicitly specified)"
    )
    # Role visibility fields
    visible_roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Roles.objects.all()),
        write_only=True,
        required=False,
        help_text="List of role IDs that can access this resource"
    )
    
    # File upload fields
    resource_file = serializers.FileField(required=True, allow_null=False)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Resources
        fields = [
            'id',
            'resource_name',
            'resource_description',
            'resource_type_detail',
            'resource_type_id',
            'uploader_user_id',  # User who uploaded the resource
            'resource_file',  # File upload field
            'file_url',  # Secure download URL
            'file_size',
            'content_type',
            'upload_datetime',
            'uploader',
            'deleted_flag',
            'deleted_datetime',
            'visible_roles',
            'role_ids'
        ]
        read_only_fields = ['id', 'upload_datetime', 'deleted_datetime', 'file_size', 'content_type']

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

    def get_file_url(self, obj):
        """Generate secure SAS URL for private blob access"""
        if not obj.resource_file:
            return None
        
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            # Generate SAS token valid for 1 hour
            sas_token = generate_blob_sas(
                account_name=settings.AZURE_ACCOUNT_NAME,
                container_name=settings.AZURE_CONTAINER,
                blob_name=obj.resource_file.name,
                account_key=settings.AZURE_ACCOUNT_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            return f"{settings.MEDIA_URL}{obj.resource_file.name}?{sas_token}"
        except Exception as e:
            # Fallback to basic URL if SAS generation fails
            return obj.resource_file.url if obj.resource_file else None
    
    def get_visible_roles(self, obj):
        """Get the roles that can access this resource"""
        from .models import ResourceRoles
        resource_roles = ResourceRoles.objects.filter(resource=obj).select_related('role')
        return RoleSerializer([rr.role for rr in resource_roles], many=True).data

    def create(self, validated_data):
        """Create resource and specify roles for visibility (ResourceRoles)"""
        role_ids = validated_data.pop('role_ids', [])
        
        # Handle file metadata and validate file type against resource type
        resource_file = validated_data.get('resource_file')
        resource_type = validated_data.get('resource_type')
        
        if resource_file and resource_type:
            # Validate file type matches resource type
            is_valid, error_message = validate_file_type_for_resource_type(
                resource_file, 
                resource_type.type_name
            )
            
            if not is_valid:
                raise serializers.ValidationError({
                    'resource_file': error_message
                })
            
            # Set file metadata
            validated_data['file_size'] = resource_file.size
            # Handle both uploaded files and ContentFile objects
            if hasattr(resource_file, 'content_type'):
                validated_data['content_type'] = resource_file.content_type
            else:
                # For ContentFile, try to detect from filename
                validated_data['content_type'] = self._detect_content_type(resource_file.name)
        
        resource = super().create(validated_data)
        
        # Assign roles to resource (ResourceRoles)
        for role_id in role_ids:
            ResourceRoles.objects.create(resource=resource, role=role_id)
        
        return resource
    
    def _detect_content_type(self, filename):
        """Detect content type from filename"""
        if not filename:
            return 'application/octet-stream'
            
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        content_type_mapping = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            'odt': 'application/vnd.oasis.opendocument.text',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'svg': 'image/svg+xml',
            'webp': 'image/webp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'wmv': 'video/x-ms-wmv',
            'flv': 'video/x-flv',
            'webm': 'video/webm',
            'mkv': 'video/x-matroska',
        }
        
        return content_type_mapping.get(file_extension, 'application/octet-stream')
    
    def _detect_resource_type(self, file):
        """Auto-detect resource type based on file extension"""
        if not file or not file.name:
            return None
            
        file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
        content_type = getattr(file, 'content_type', None) or self._detect_content_type(file.name)
        
        # Mapping of file extensions and content types to resource types
        type_mapping = {
            # Documents/Guides/Templates (all accept the same file types)
            'pdf': 'document',
            'doc': 'document', 
            'docx': 'document',
            'txt': 'document',
            'rtf': 'document',
            'odt': 'document',
            'xls': 'document',
            'xlsx': 'document',
            'ppt': 'document',
            'pptx': 'document',
            
            # Images
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'bmp': 'image',
            'svg': 'image',
            'webp': 'image',
            'tiff': 'image',
            'tif': 'image',
            
            # Videos
            'mp4': 'video',
            'avi': 'video',
            'mov': 'video',
            'wmv': 'video',
            'flv': 'video',
            'webm': 'video',
            'mkv': 'video',
        }
        
        # Check by file extension first
        if file_extension in type_mapping:
            type_name = type_mapping[file_extension]
        # Check by content type
        elif 'application/pdf' in content_type:
            type_name = 'document'
        elif 'application/msword' in content_type or 'application/vnd.openxmlformats-officedocument.wordprocessingml' in content_type:
            type_name = 'document'
        elif 'application/vnd.ms-excel' in content_type or 'application/vnd.openxmlformats-officedocument.spreadsheetml' in content_type:
            type_name = 'document'
        elif 'application/vnd.ms-powerpoint' in content_type or 'application/vnd.openxmlformats-officedocument.presentationml' in content_type:
            type_name = 'document'
        elif 'image/' in content_type:
            type_name = 'image'
        elif 'video/' in content_type:
            type_name = 'video'
        elif 'text/' in content_type:
            type_name = 'document'
        else:
            # Default to document for unknown types
            type_name = 'document'
        
        # Get or create the resource type
        try:
            from .models import ResourceType
            return ResourceType.objects.get(type_name=type_name)
        except ResourceType.DoesNotExist:
            # Create the type if it doesn't exist
            return ResourceType.objects.create(
                type_name=type_name,
                type_description=f'Auto-detected type for {type_name} files'
            )

    def update(self, instance, validated_data):
        """Update resource and roles"""
        role_ids = validated_data.pop('role_ids', None)
        
        # Handle file metadata if a new file is uploaded
        resource_file = validated_data.get('resource_file')
        if resource_file:
            validated_data['file_size'] = resource_file.size
            validated_data['content_type'] = resource_file.content_type
        
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
    resource_type_detail = ResourceTypeSerializer(source='resource_type', read_only=True)
    visible_roles = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resources
        fields = [
            'id',
            'resource_name',
            'resource_description',
            'resource_type_detail',
            'upload_datetime',
            'uploader',
            'visible_roles',
            'resource_file',
            'file_url',
            'file_size',
            'content_type'
        ]
    
    def get_file_url(self, obj):
        """Generate secure SAS URL for private blob access"""
        if not obj.resource_file:
            return None
        
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            from datetime import datetime, timedelta
            
            sas_token = generate_blob_sas(
                account_name=settings.AZURE_ACCOUNT_NAME,
                container_name=settings.AZURE_CONTAINER,
                blob_name=obj.resource_file.name,
                account_key=settings.AZURE_ACCOUNT_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            return f"{settings.MEDIA_URL}{obj.resource_file.name}?{sas_token}"
        except Exception as e:
            # Fallback to basic URL if SAS generation fails
            return obj.resource_file.url if obj.resource_file else None
    
    def get_visible_roles(self, obj):
        """Get the roles that can access this resource"""
        # Use prefetched data if available
        if hasattr(obj, '_prefetched_objects_cache') and 'resourceroles' in obj._prefetched_objects_cache:
            resource_roles = obj.resourceroles.all()
            return RoleSerializer([rr.role for rr in resource_roles], many=True).data
        # Otherwise query directly
        from .models import ResourceRoles
        resource_roles = ResourceRoles.objects.filter(resource=obj).select_related('role')
        return RoleSerializer([rr.role for rr in resource_roles], many=True).data
