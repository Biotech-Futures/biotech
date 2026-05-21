from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime
from io import BytesIO
import re
import os
import tempfile

from django.core.files.base import ContentFile
from django.db.models import Q, F, Exists, OuterRef, Value, CharField
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from apps.resources.models import Resources, ResourceAudience, Roles, ResourceType, ResourceLabel
from apps.resources.services.storage import RESOURCE_FILE_SERVICE
from apps.groups.models import Tracks, Groups
from apps.users.models import User
from azure_blob_utils import (
    upload_file,
    download_file_text,
    download_file_bytes,
)
from azure.storage.blob import BlobServiceClient
from apps.admin.scope_utils import get_admin_track_ids


# Constants
ADMIN_ROLE_SLUG = "admin"
RESOURCE_KIND_FILE = "file"
RESOURCE_KIND_PAGE = "page"
VISIBILITY_GLOBAL = "global"
VISIBILITY_TRACK_BASED = "track_based"
VISIBILITY_ROLE_BASED = "role_based"


# Type definitions
class RoleDict(TypedDict):
    id: int
    slug: str
    type_name: Optional[str]


class ResourceUploaderDict(TypedDict):
    id: int
    first_name: str
    last_name: str
    email: str


class AuthUploaderDict(TypedDict):
    id: Optional[str]
    type_name: Optional[str]
    email: Optional[str]


class ResourceRowDict(TypedDict):
    id: int
    uploader_user_id: int
    track_id: Optional[int]
    visibility_scope: str
    uploaded_at: str
    deleted_at: Optional[str]
    resource_kind: str
    resource_name: str
    resource_description: Optional[str]
    resource_type: Optional[str]
    content_html: Optional[str]
    file_name: Optional[str]
    file_mime_type: Optional[str]
    file_size: Optional[int]
    storage_key: Optional[str]
    group_id: Optional[int]
    resource_type_id: Optional[int]


class ResourceAudienceDict(TypedDict):
    id: int
    resource_id: int
    role_id: Optional[int]
    track_id: Optional[int]
    role: Optional[RoleDict]


class ResourceDict(ResourceRowDict):
    uploader: ResourceUploaderDict
    audiences: List[ResourceAudienceDict]


class QueryResourcesInput(TypedDict):
    page: int
    limit: int
    uploader_user_id: Optional[int]
    group_id: Optional[int]
    resource_kind: Optional[str]
    resource_type_id: Optional[int]
    resource_type: Optional[str]
    track_id: Optional[int]
    search: Optional[str]
    order: str
    sort_by: Optional[str]
    sort_order: str
    uploader: Optional[str]
    role_slug: Optional[str]


class CreateResourceInput(TypedDict):
    resource_kind: Optional[str]
    resource_name: str
    resource_description: Optional[str]
    resource_type: Optional[str]
    resource_type_id: Optional[int]
    visibility_scope: Optional[str]
    track_id: Optional[int]
    group_id: Optional[int]
    role_ids: Optional[List[int]]
    content_html: Optional[str]


class UpdateResourceInput(TypedDict):
    resource_kind: Optional[str]
    resource_name: Optional[str]
    resource_description: Optional[str]
    resource_type: Optional[str]
    resource_type_id: Optional[int]
    visibility_scope: Optional[str]
    track_id: Optional[int]
    group_id: Optional[int]
    role_ids: Optional[List[int]]
    content_html: Optional[str]


# Helper functions

def slugify_role(value: str) -> str:
    """Convert role name to slug format."""
    slug = value.strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug


def normalize_role_ids(
    role_ids: Optional[List[int]] = None,
    available_roles: Optional[List[RoleDict]] = None,
) -> List[int]:
    """Normalize role IDs, ensuring admin role is included."""
    if role_ids is None:
        role_ids = []
    if available_roles is None:
        available_roles = []
    
    admin_role = next(
        (r for r in available_roles if r['slug'] == ADMIN_ROLE_SLUG),
        None
    )
    
    available_role_ids = {r['id'] for r in available_roles}
    valid_ids = [rid for rid in role_ids if rid in available_role_ids]
    
    result = valid_ids.copy()
    if admin_role:
        result.append(admin_role['id'])
    
    return list(set(result))


def resolve_visibility_scope(
    track_id: Optional[int] = None,
    role_ids: Optional[List[int]] = None,
) -> str:
    """Determine visibility scope based on track and role assignments."""
    if role_ids:
        return VISIBILITY_ROLE_BASED
    if track_id is not None:
        return VISIBILITY_TRACK_BASED
    return VISIBILITY_GLOBAL


def normalize_visibility_scope(
    value: Optional[str],
    track_id: Optional[int],
    role_ids: Optional[List[int]] = None,
) -> str:
    """Normalize visibility scope value."""
    if value in (VISIBILITY_GLOBAL, VISIBILITY_TRACK_BASED, VISIBILITY_ROLE_BASED):
        return value
    return resolve_visibility_scope(track_id, role_ids)


def build_storage_key(resource_id: int, file_name: Optional[str] = None) -> str:
    """Build a unique storage key for blob storage."""
    stamp = int(timezone.now().timestamp() * 1000)
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name or "resource.bin")
    return f"resources/{stamp}-{resource_id}-{safe_name}"


def extract_file_name_from_storage_key(storage_key: Optional[str]) -> Optional[str]:
    """Extract original filename from storage key."""
    if not storage_key:
        return None
    parts = storage_key.split("/")
    raw = parts[-1] if parts else ""
    dash_index = raw.find("-", raw.find("-") + 1)
    if dash_index == -1:
        return raw or None
    return raw[dash_index + 1:] or None


def stream_blob_chunks(download_stream):
    """Yield Azure blob chunks for a Django streaming response."""
    for chunk in download_stream.chunks():
        yield chunk


def _configured_resource_container_names() -> List[str]:
    """Return resource containers in read-preference order.

    Older admin upload code writes through azure_blob_utils, which uses
    AZURE_CONTAINER. Newer managed resource storage reads from
    AZURE_RESOURCE_CONTAINER. Trying both keeps existing uploads readable while
    still preferring the resource-specific container.
    """
    names = [
        getattr(settings, "AZURE_STORAGE_CONTAINER_NAME", ""),
        getattr(settings, "AZURE_RESOURCE_CONTAINER", ""),
        getattr(settings, "AZURE_CONTAINER", ""),
    ]
    ordered = []
    for name in names:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _get_blob_service_client():
    """Build an Azure blob service client from the configured credentials."""
    connection_string = (
        getattr(settings, "AZURE_CONNECTION_STRING", "")
        or getattr(settings, "AZURE_STORAGE_CONNECTION_STRING", "")
    )
    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)
    return BlobServiceClient(
        f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=settings.AZURE_ACCOUNT_KEY,
    )


def iter_resource_blob_clients(storage_key: str):
    """Yield blob clients for all configured resource storage containers."""
    blob_service_client = _get_blob_service_client()
    for container_name in _configured_resource_container_names():
        container_client = blob_service_client.get_container_client(container_name)
        yield container_client.get_blob_client(storage_key)


def get_resource_blob_client(storage_key: str):
    """Build a blob client for the preferred resource storage container."""
    return next(iter_resource_blob_clients(storage_key))


def get_page_content_html(resource: Resources) -> Optional[str]:
    """Read stored HTML for page resources."""
    if resource.kind != RESOURCE_KIND_PAGE or not resource.storage_key:
        return None

    try:
        with RESOURCE_FILE_SERVICE.open(resource.storage_key) as fp:
            raw = fp.read()
        if isinstance(raw, bytes):
            return raw.decode('utf-8', errors='replace')
        return raw
    except Exception:
        try:
            return download_file_text(resource.storage_key)
        except Exception:
            return None


def resource_to_row(resource: Resources, include_page_content: bool = False) -> ResourceRowDict:
    track_id = resource.track_id
    if not track_id and resource.group:
        track_id = resource.group.track_id

    return {
        'id': resource.id,
        'uploader_user_id': resource.uploaded_by_id,
        'group_id': resource.group_id,
        'track_id': track_id,
        'visibility_scope': resource.visibility_scope,
        'uploaded_at': resource.uploaded_at.isoformat(),
        'deleted_at': resource.deleted_at.isoformat() if resource.deleted_at else None,
        'resource_kind': resource.kind,
        'resource_name': resource.name,
        'resource_description': resource.description,
        'resource_type_id': resource.type_id,
        'resource_type': resource.type.type_name if resource.type else None,
        'content_html': get_page_content_html(resource) if include_page_content else None,
        'file_name': None,
        'file_mime_type': resource.file_mime_type,
        'file_size': resource.file_size,
        'storage_key': resource.storage_key,
    }


def get_roles_from_db() -> List[RoleDict]:
    """Fetch all roles from database."""
    roles = Roles.objects.all().order_by('id')
    return [
        {
            'id': role.id,
            'type_name': role.role_name,
            'slug': slugify_role(role.role_name),
        }
        for role in roles
    ]


def resolve_uploader_for_db(
    auth_uploader: Optional[AuthUploaderDict] = None,
) -> ResourceUploaderDict:
    """Resolve uploader user from auth context or database."""
    if auth_uploader and auth_uploader.get('id'):
        try:
            user_id = int(auth_uploader['id'])
            user = User.objects.get(id=user_id)
            return {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
        except (ValueError, User.DoesNotExist):
            pass
    
    if auth_uploader and auth_uploader.get('email'):
        try:
            user = User.objects.get(email=auth_uploader['email'])
            return {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
        except User.DoesNotExist:
            pass
    
    # Fallback to first user
    user = User.objects.order_by('id').first()
    if not user:
        raise ValueError("Cannot resolve uploader: no users in database")
    
    return {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
    }


def fetch_resources_from_db(params: QueryResourcesInput, requesting_user=None) -> List[ResourceRowDict]:
    """Fetch resources from database with filters and pagination."""
    queryset = Resources.objects.select_related(
        'type', 'track', 'group', 'uploaded_by'
    ).filter(deleted_at__isnull=True)

    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        queryset = queryset.filter(
            Q(track_id__in=track_ids) | Q(track__isnull=True, group__track_id__in=track_ids) |
            Q(track__isnull=True, group__isnull=True)
        )
    
    # Apply filters
    if params.get('uploader_user_id'):
        queryset = queryset.filter(uploaded_by_id=params['uploader_user_id'])
    
    if params.get('group_id') is not None:
        queryset = queryset.filter(group_id=params['group_id'])
    
    if params.get('resource_kind'):
        queryset = queryset.filter(kind=params['resource_kind'])
    
    if params.get('resource_type_id'):
        queryset = queryset.filter(type_id=params['resource_type_id'])
    
    if params.get('resource_type'):
        queryset = queryset.filter(type__type_name=params['resource_type'])
    
    if params.get('track_id'):
        # Use COALESCE-like logic: resource track or group track
        queryset = queryset.filter(
            Q(track_id=params['track_id']) |
            Q(group__track_id=params['track_id'])
        )
    
    if params.get('search'):
        pattern = params['search']
        queryset = queryset.filter(
            Q(name__icontains=pattern) |
            Q(description__icontains=pattern)
        )
    
    # Order
    order_by = params.get('order', 'newest')
    if order_by == 'oldest':
        queryset = queryset.order_by('uploaded_at', 'name')
    else:
        queryset = queryset.order_by('-uploaded_at', 'name')
    
    return [resource_to_row(resource) for resource in queryset]


def fetch_resource_by_id_from_db(resource_id: int) -> Optional[ResourceRowDict]:
    """Fetch single resource from database by ID."""
    try:
        resource = Resources.objects.select_related(
            'type', 'track', 'group', 'uploaded_by'
        ).get(id=resource_id, deleted_at__isnull=True)
    except Resources.DoesNotExist:
        return None
    
    return resource_to_row(resource, include_page_content=True)


def hydrate_resources(resource_rows: List[ResourceRowDict]) -> List[ResourceDict]:
    """Hydrate resource rows with uploader and audience information."""
    if not resource_rows:
        return []
    
    # Fetch uploaders
    uploader_ids = {row['uploader_user_id'] for row in resource_rows}
    users = User.objects.filter(id__in=uploader_ids)
    uploader_map = {
        user.id: {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
        for user in users
    }
    
    # Fetch audiences
    resource_ids = [row['id'] for row in resource_rows]
    audiences_qs = ResourceAudience.objects.filter(
        resource_id__in=resource_ids
    ).select_related('role', 'track')
    
    audience_map: Dict[int, List[ResourceAudienceDict]] = {}
    for audience in audiences_qs:
        resource_id = audience.resource_id
        if resource_id not in audience_map:
            audience_map[resource_id] = []

        role_data = None
        if audience.role:
            role_data = {
                'id': audience.role.id,
                'slug': slugify_role(audience.role.role_name),
                'type_name': audience.role.role_name,
            }

        audience_map[resource_id].append({
            'id': audience.id,
            'resource_id': resource_id,
            'role_id': audience.role_id,
            'track_id': audience.track_id,
            'role': role_data,
        })

    # Fetch labels via M2M through table
    through_rows = Resources.labels.through.objects.filter(
        resources_id__in=resource_ids
    ).values('resources_id', 'resourcelabel_id')
    label_ids_by_resource: Dict[int, List[int]] = {}
    all_label_ids: set = set()
    for row in through_rows:
        rid, lid = row['resources_id'], row['resourcelabel_id']
        label_ids_by_resource.setdefault(rid, []).append(lid)
        all_label_ids.add(lid)
    labels_by_id = {
        lbl.id: {'id': lbl.id, 'name': lbl.name}
        for lbl in ResourceLabel.objects.filter(id__in=all_label_ids)
    }
    label_map: Dict[int, List[Dict]] = {
        rid: [labels_by_id[lid] for lid in lids if lid in labels_by_id]
        for rid, lids in label_ids_by_resource.items()
    }
    
    # Build complete resources
    result = []
    for row in resource_rows:
        audiences = audience_map.get(row['id'], [])
        
        # Determine visibility scope
        role_ids = [a['role_id'] for a in audiences if a['role_id']]
        visibility = normalize_visibility_scope(
            row['visibility_scope'],
            row['track_id'],
            role_ids,
        )
        
        # Get uploader
        uploader = uploader_map.get(row['uploader_user_id'])
        if not uploader:
            uploader = {
                'id': row['uploader_user_id'],
                'first_name': 'Unknown',
                'last_name': 'User',
                'email': 'unknown@example.com',
            }
        
        resource = {
            **row,
            'visibility_scope': visibility,
            'file_name': row['file_name'] or extract_file_name_from_storage_key(row['storage_key']),
            'uploader': uploader,
            'audiences': audiences,
            'labels': label_map.get(row['id'], []),
        }
        result.append(resource)

    return result


# Main service functions

def query_resources(params: QueryResourcesInput, requesting_user=None) -> Dict[str, Any]:
    """Query resources with pagination and filtering."""
    page = params.get('page', 1)
    limit = params.get('limit', 10)
    offset = (page - 1) * limit

    # Fetch from database
    resource_rows = fetch_resources_from_db(params, requesting_user=requesting_user)
    resources_list = hydrate_resources(resource_rows)
    
    # Apply client-side filters
    search = params.get('search', '').lower() if params.get('search') else ''
    if search:
        resources_list = [
            r for r in resources_list
            if search in f"{r['resource_name']} {r['resource_description'] or ''}".lower()
        ]
    
    uploader = params.get('uploader', '').lower() if params.get('uploader') else ''
    if uploader:
        resources_list = [
            r for r in resources_list
            if uploader in f"{r['uploader']['first_name']} {r['uploader']['last_name']}".lower()
            or uploader in r['uploader']['email'].lower()
        ]
    
    role_slug = params.get('role_slug', '').lower() if params.get('role_slug') else ''
    if role_slug:
        resources_list = [
            r for r in resources_list
            if any(
                role_slug in (a['role']['slug'] or '').lower()
                for a in r['audiences']
                if a['role']
            )
        ]
    
    # Sort. ``order`` is the legacy uploaded-time control; sortBy/sortOrder is
    # used by clickable table headers.
    order = params.get('order', 'newest')
    sort_by = params.get('sort_by')
    sort_order = params.get('sort_order', 'desc')
    def get_timestamp(resource: ResourceDict) -> float:
        try:
            return datetime.fromisoformat(resource['uploaded_at']).timestamp()
        except (ValueError, TypeError):
            return 0

    def get_role_label(resource: ResourceDict) -> str:
        return ", ".join(
            sorted(
                {
                    a["role"]["slug"]
                    for a in resource["audiences"]
                    if a.get("role") and a["role"].get("slug") != ADMIN_ROLE_SLUG
                }
            )
        )

    def get_track_label(resource: ResourceDict) -> str:
        return str(resource.get("track_id") or "")

    sort_getters = {
        "name": lambda r: r["resource_name"] or "",
        "type_name": lambda r: r["resource_type"] or "",
        "visibility": lambda r: r["visibility_scope"] or "",
        "role": get_role_label,
        "track": get_track_label,
        "uploader": lambda r: f"{r['uploader']['first_name']} {r['uploader']['last_name']} {r['uploader']['email']}",
        "uploaded_at": lambda r: get_timestamp(r),
    }

    if sort_by in sort_getters:
        reverse = sort_order == "desc"
        resources_list.sort(
            key=lambda r: (sort_getters[sort_by](r), r["resource_name"]),
            reverse=reverse,
        )
    elif order == 'oldest':
        resources_list.sort(key=lambda r: (get_timestamp(r), r['resource_name']))
    else:
        resources_list.sort(
            key=lambda r: (-get_timestamp(r), r['resource_name'])
        )
    
    # Paginate
    total = len(resources_list)
    items = resources_list[offset:offset + limit]
    
    return {
        'msg': 'Resources retrieved successfully',
        'data': {
            'items': items,
            'total': total,
            'page': page,
            'limit': limit,
            'hasMore': offset + limit < total,
        },
    }


def query_resource_by_id(resource_id: int) -> Dict[str, Any]:
    """Query single resource by ID."""
    resource_row = fetch_resource_by_id_from_db(resource_id)
    
    if not resource_row:
        return {
            'msg': 'Resource not found',
            'data': None,
        }
    
    resources = hydrate_resources([resource_row])
    resource = resources[0] if resources else None
    
    return {
        'msg': 'Resource retrieved successfully',
        'data': resource,
    }


@transaction.atomic
def create_resource(
    payload: CreateResourceInput,
    uploader: Optional[AuthUploaderDict] = None,
) -> Dict[str, Any]:
    """Create a new resource."""
    uploader_profile = resolve_uploader_for_db(uploader)
    available_roles = get_roles_from_db()
    
    requested_role_ids = payload.get('role_ids', [])
    role_ids = normalize_role_ids(requested_role_ids, available_roles)
    
    requested_resource_type = payload.get('resource_type')
    resource_type_id = payload.get('resource_type_id')
    
    if requested_resource_type and not resource_type_id:
        try:
            rt = ResourceType.objects.get(type_name=requested_resource_type)
            resource_type_id = rt.id
        except ResourceType.DoesNotExist:
            resource_type_id = None
    
    visibility_scope = normalize_visibility_scope(
        payload.get('visibility_scope'),
        payload.get('track_id'),
        requested_role_ids,
    )
    
    resource = Resources.objects.create(
        name=payload['resource_name'],
        description=payload.get('resource_description', ''),
        kind=payload.get('resource_kind', RESOURCE_KIND_FILE),
        type_id=resource_type_id,
        uploaded_by_id=uploader_profile['id'],
        visibility_scope=visibility_scope,
        track_id=payload.get('track_id'),
        group_id=payload.get('group_id'),
        uploaded_at=timezone.now(),
    )
    
    # Handle page resources with HTML content
    if payload.get('resource_kind') == RESOURCE_KIND_PAGE:
        html_text = payload.get('content_html', '')
        file_name = f"{payload.get('resource_name', 'resource')}.html"
        html_bytes = html_text.encode('utf-8')
        storage_key = RESOURCE_FILE_SERVICE.save_content(file_name, ContentFile(html_bytes))
        
        resource.storage_key = storage_key
        resource.file_mime_type = 'text/html'
        resource.file_size = len(html_bytes)
        resource.save()
    
    # Assign roles
    if role_ids:
        ResourceAudience.objects.bulk_create([
            ResourceAudience(
                resource_id=resource.id,
                role_id=role_id,
                track_id=payload.get('track_id'),
            )
            for role_id in role_ids
        ])

    # Assign labels
    label_names = payload.get('label_names') or []
    if label_names:
        labels = [
            ResourceLabel.objects.get_or_create(name=name.strip())[0]
            for name in label_names if name.strip()
        ]
        resource.labels.set(labels)

    return query_resource_by_id(resource.id)


@transaction.atomic
def upload_resource(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Upload a file resource."""
    uploader_profile = resolve_uploader_for_db(payload.get('uploader'))
    available_roles = get_roles_from_db()
    
    requested_role_ids = payload.get('role_ids', [])
    role_ids = normalize_role_ids(requested_role_ids, available_roles)
    
    requested_resource_type = payload.get('resource_type')
    resource_type_id = payload.get('resource_type_id')
    
    if requested_resource_type and not resource_type_id:
        try:
            rt = ResourceType.objects.get(type_name=requested_resource_type)
            resource_type_id = rt.id
        except ResourceType.DoesNotExist:
            resource_type_id = None
    
    file_mime_type = payload.get('file_mime_type', 'application/octet-stream')
    
    visibility_scope = normalize_visibility_scope(
        payload.get('visibility_scope'),
        payload.get('track_id'),
        requested_role_ids,
    )
    
    resource = Resources.objects.create(
        name=payload['resource_name'],
        description=payload.get('resource_description', ''),
        kind=RESOURCE_KIND_FILE,
        type_id=resource_type_id,
        uploaded_by_id=uploader_profile['id'],
        visibility_scope=visibility_scope,
        track_id=payload.get('track_id'),
        group_id=payload.get('group_id'),
        file_mime_type=file_mime_type,
        file_size=payload.get('file_size', 0),
        uploaded_at=timezone.now(),
    )
    
    # Upload file to blob storage
    storage_key = build_storage_key(resource.id, payload.get('file_name', 'file'))
    file_bytes = payload.get('file_bytes', b'')
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        if isinstance(file_bytes, bytes):
            tmp.write(file_bytes)
        else:
            tmp.write(bytes(file_bytes))
        tmp.flush()
        try:
            upload_file(tmp.name, storage_key)
        finally:
            os.unlink(tmp.name)
    
    resource.storage_key = storage_key
    resource.save()
    
    # Assign roles
    if role_ids:
        ResourceAudience.objects.bulk_create([
            ResourceAudience(
                resource_id=resource.id,
                role_id=role_id,
                track_id=payload.get('track_id'),
            )
            for role_id in role_ids
        ])
    
    return query_resource_by_id(resource.id)


@transaction.atomic
def replace_resource_file(
    resource_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Replace file in existing resource."""
    existing = query_resource_by_id(resource_id)
    if not existing.get('data'):
        return {
            'msg': 'Resource not found',
            'data': None,
        }
    
    resource_data = existing['data']
    if resource_data['resource_kind'] == RESOURCE_KIND_PAGE:
        return {
            'msg': 'HTML page resource cannot replace file',
            'data': None,
        }
    
    resource = Resources.objects.get(id=resource_id)
    next_storage_key = build_storage_key(resource_id, payload.get('file_name', 'file'))
    
    # Upload new file
    file_bytes = payload.get('file_bytes', b'')
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        if isinstance(file_bytes, bytes):
            tmp.write(file_bytes)
        else:
            tmp.write(bytes(file_bytes))
        tmp.flush()
        try:
            upload_file(tmp.name, next_storage_key)
        finally:
            os.unlink(tmp.name)
    
    resource.storage_key = next_storage_key
    resource.file_mime_type = payload.get('file_mime_type', 'application/octet-stream')
    resource.file_size = payload.get('file_size', 0)
    resource.save()
    
    return query_resource_by_id(resource_id)


def download_resource(resource_id: int) -> Dict[str, Any]:
    """Download resource file."""
    try:
        resource = Resources.objects.get(id=resource_id, deleted_at__isnull=True)
    except Resources.DoesNotExist:
        return {
            'msg': 'Resource not found',
            'data': None,
        }

    if not resource.storage_key:
        return {
            'msg': 'This resource has no uploaded file',
            'data': None,
        }

    try:
        try:
            content = download_file_bytes(resource.storage_key)
        except Exception:
            content = None
            for blob_client in iter_resource_blob_clients(resource.storage_key):
                try:
                    if blob_client.exists():
                        content = blob_client.download_blob().readall()
                        break
                except Exception:
                    continue
            if content is None:
                raise

        return {
            'msg': 'Resource download ready',
            'data': {
                'file_name': extract_file_name_from_storage_key(resource.storage_key) or f"resource-{resource_id}",
                'mime_type': resource.file_mime_type or 'application/octet-stream',
                'content': content,
            },
        }
    except Exception as e:
        return {
            'msg': 'File not found in storage',
            'data': None,
        }


def access_resource(resource_id: int) -> Dict[str, Any]:
    """Open a resource blob for inline streaming."""
    try:
        resource = Resources.objects.get(id=resource_id, deleted_at__isnull=True)
    except Resources.DoesNotExist:
        return {
            'msg': 'Resource not found',
            'data': None,
        }

    if not resource.storage_key:
        return {
            'msg': 'This resource has no uploaded file',
            'data': None,
        }

    file_name = extract_file_name_from_storage_key(resource.storage_key) or f"resource-{resource_id}"

    try:
        for blob_client in iter_resource_blob_clients(resource.storage_key):
            try:
                if blob_client.exists():
                    break
            except Exception:
                continue
        else:
            return {
                'msg': 'File not found in storage',
                'data': None,
            }

        properties = blob_client.get_blob_properties()
        content_settings = getattr(properties, "content_settings", None)
        storage_content_type = getattr(content_settings, "content_type", None)
        mime_type = (
            resource.file_mime_type
            or storage_content_type
            or 'application/octet-stream'
        )
        download_stream = blob_client.download_blob()
        file_size = resource.file_size or getattr(properties, "size", None)

        return {
            'msg': 'Resource stream ready',
            'data': {
                'resource_id': resource.id,
                'access_type': 'stream',
                'file_name': file_name,
                'mime_type': mime_type,
                'file_size': file_size,
                'stream': stream_blob_chunks(download_stream),
            },
        }
    except Exception:
        return {
            'msg': 'File not found in storage',
            'data': None,
        }


@transaction.atomic
def update_resource(
    resource_id: int,
    updates: UpdateResourceInput,
) -> Dict[str, Any]:
    """Update resource metadata."""
    existing = query_resource_by_id(resource_id)
    if not existing.get('data'):
        return {'msg': 'Resource not found', 'data': None}
    
    resource_data = existing['data']
    resource = Resources.objects.get(id=resource_id)
    
    # Update basic fields
    if 'resource_name' in updates:
        resource.name = updates['resource_name']
    if 'resource_description' in updates:
        resource.description = updates['resource_description'] or ''
    if 'visibility_scope' in updates:
        resource.visibility_scope = updates['visibility_scope']
    if 'track_id' in updates:
        resource.track_id = updates['track_id']
    if 'group_id' in updates:
        resource.group_id = updates['group_id']
    if 'resource_kind' in updates:
        resource.kind = updates['resource_kind']
    
    # Update resource type
    if 'resource_type' in updates:
        if updates['resource_type']:
            try:
                rt = ResourceType.objects.get(type_name=updates['resource_type'])
                resource.type_id = rt.id
            except ResourceType.DoesNotExist:
                pass
    elif 'resource_type_id' in updates:
        resource.type_id = updates['resource_type_id']
    
    resource.save()
    
    # Handle page content update
    if updates.get('resource_kind') == RESOURCE_KIND_PAGE and 'content_html' in updates:
        html_text = updates['content_html'] or ''
        file_name = f"{(updates.get('resource_name') or resource_data['resource_name']) or 'resource'}.html"
        html_bytes = html_text.encode('utf-8')
        storage_key = RESOURCE_FILE_SERVICE.save_content(file_name, ContentFile(html_bytes))
        
        resource.storage_key = storage_key
        resource.file_mime_type = 'text/html'
        resource.file_size = len(html_bytes)
        resource.save()
    
    # Update audiences/roles
    if 'role_ids' in updates:
        available_roles = get_roles_from_db()
        requested_role_ids = updates['role_ids'] or []
        role_ids = normalize_role_ids(requested_role_ids, available_roles)

        ResourceAudience.objects.filter(resource_id=resource_id).delete()
        if role_ids:
            ResourceAudience.objects.bulk_create([
                ResourceAudience(
                    resource_id=resource_id,
                    role_id=role_id,
                    track_id=updates.get('track_id') or resource_data['track_id'],
                )
                for role_id in role_ids
            ])

    # Update labels
    if 'label_names' in updates:
        label_names = updates['label_names'] or []
        labels = [
            ResourceLabel.objects.get_or_create(name=name.strip())[0]
            for name in label_names if name.strip()
        ]
        resource.labels.set(labels)

    return query_resource_by_id(resource_id)


@transaction.atomic
def delete_resource(resource_id: int) -> Dict[str, Any]:
    """Soft delete resource."""
    existing = query_resource_by_id(resource_id)
    if not existing.get('data'):
        return {'msg': 'Resource not found', 'data': None}
    
    resource = Resources.objects.get(id=resource_id)
    resource.deleted_at = timezone.now()
    resource.save()
    
    return {
        'msg': 'Resource deleted successfully',
        'data': None,
    }


@transaction.atomic
def assign_role_to_resource(resource_id: int, role_id: int) -> Dict[str, Any]:
    """Assign a role to resource audience."""
    # Check role exists
    try:
        Roles.objects.get(id=role_id)
    except Roles.DoesNotExist:
        return {'msg': 'Role not found', 'data': None}
    
    # Check resource exists
    try:
        resource = Resources.objects.get(id=resource_id, deleted_at__isnull=True)
    except Resources.DoesNotExist:
        return {'msg': 'Resource not found', 'data': None}
    
    # Avoid duplicates
    ResourceAudience.objects.get_or_create(
        resource_id=resource_id,
        role_id=role_id,
    )
    
    return query_resource_by_id(resource_id)


@transaction.atomic
def remove_role_from_resource(resource_id: int, role_id: int) -> Dict[str, Any]:
    """Remove a role from resource audience."""
    available_roles = get_roles_from_db()
    admin_role = next(
        (r for r in available_roles if r['slug'] == ADMIN_ROLE_SLUG),
        None
    )
    
    if admin_role and role_id == admin_role['id']:
        existing = query_resource_by_id(resource_id)
        return {
            'msg': 'Admin visibility is required and cannot be removed',
            'data': existing.get('data'),
        }
    
    try:
        Resources.objects.get(id=resource_id, deleted_at__isnull=True)
    except Resources.DoesNotExist:
        return {'msg': 'Resource not found', 'data': None}
    
    ResourceAudience.objects.filter(
        resource_id=resource_id,
        role_id=role_id,
    ).delete()
    
    return query_resource_by_id(resource_id)


def list_resource_roles() -> Dict[str, Any]:
    """List all available roles."""
    roles = get_roles_from_db()
    return {
        'msg': 'Roles retrieved successfully',
        'data': roles,
    }


def list_resource_types() -> Dict[str, Any]:
    """List all resource types."""
    types = ResourceType.objects.all().order_by('type_name')
    
    if not types.exists():
        return {
            'msg': 'Resource types retrieved successfully',
            'data': [],
        }
    
    return {
        'msg': 'Resource types retrieved successfully',
        'data': [
            {
                'id': rt.id,
                'value': rt.type_name,
                'label': rt.type_name,
            }
            for rt in types
        ],
    }


def list_resource_tracks(requesting_user=None) -> Dict[str, Any]:
    """List all resource tracks."""
    qs = Tracks.objects.all()
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        qs = qs.filter(id__in=track_ids)
    tracks = qs.order_by('track_name')

    return {
        'msg': 'Tracks retrieved successfully',
        'data': [
            {
                'id': track.id,
                'code': track.track_name,
                'label': track.track_name,
            }
            for track in tracks
        ],
    }
