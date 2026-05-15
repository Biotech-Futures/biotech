from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime

from django.db.models import Q, F, Count, Exists, OuterRef, query
from django.utils import timezone
from django.db import transaction

from apps.events.models import Events, EventRsvp, EventTargetGroup, EventTargetRole, EventTargetTrack
from apps.groups.models import Groups, Tracks
from apps.resources.models import Roles
from apps.users.models import User
from apps.admin.scope_utils import get_admin_track_ids


# Type definitions
class EventResponseDict(TypedDict):
    msg: str
    data: Optional[Any]


class PaginatedEventResponse(TypedDict):
    msg: str
    data: Dict[str, Any]


class EventTargetsResponseDict(TypedDict):
    msg: str
    data: Optional[Dict[str, List[int]]]


class QueryEventsInput(TypedDict, total=False):
    page: int
    limit: int
    host_user_id: Optional[int]
    upcoming: bool


class CreateEventInput(TypedDict, total=False):
    event_name: str
    description: Optional[str]
    location: Optional[str]
    humanitix_link: Optional[str]
    is_virtual: bool
    host_user_id: int
    start_at: str
    ends_at: str
    target_group_ids: Optional[List[int]]
    target_role_ids: Optional[List[int]]
    target_track_ids: Optional[List[int]]


class UpdateEventInput(TypedDict, total=False):
    event_name: Optional[str]
    description: Optional[str]
    location: Optional[str]
    humanitix_link: Optional[str]
    is_virtual: bool
    host_user_id: Optional[int]
    start_at: Optional[str]
    ends_at: Optional[str]
    target_group_ids: Optional[List[int]]
    target_role_ids: Optional[List[int]]
    target_track_ids: Optional[List[int]]


class CreateEventRsvpInput(TypedDict):
    user_id: int
    rsvp_status: str


class UpdateEventRsvpInput(TypedDict):
    rsvp_status: str


def _to_event_id(id_str: str) -> Optional[int]:
    """Convert string ID to integer event ID."""
    try:
        event_id = int(id_str)
        if event_id <= 0:
            return None
        return event_id
    except (ValueError, TypeError):
        return None


def _event_to_camel(event: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw Django values() dict to camelCase for the frontend."""
    host_first_name = (event.get("host_user__first_name") or "").strip()
    host_last_name = (event.get("host_user__last_name") or "").strip()
    host_email = event.get("host_user__email")
    host_name = f"{host_first_name} {host_last_name}".strip() or host_email

    return {
        "id": event["id"],
        "eventName": event.get("event_name"),
        "description": event.get("description"),
        "startDatetime": event.get("start_datetime").isoformat() if event.get("start_datetime") else None,
        "endsDatetime": event.get("ends_datetime").isoformat() if event.get("ends_datetime") else None,
        "location": event.get("location"),
        "deletedFlag": event.get("deleted_at") is not None,
        "deletedDatetime": event.get("deleted_at").isoformat() if event.get("deleted_at") else None,
        "eventImage(img)": event.get("event_image"),
        "isVirtual": event.get("is_virtual", False),
        "hostUserId": event.get("host_user_id"),
        "hostName": host_name,
        "hostEmail": host_email,
        "locationLink": event.get("location_link"),
    }


def query_events(params: QueryEventsInput, requesting_user=None) -> PaginatedEventResponse:
    """
    Query events with pagination and filtering.

    Args:
        params: Dictionary with page, limit, host_user_id, and upcoming filters
        requesting_user: The admin user making the request (for scope filtering)

    Returns:
        Dictionary with events list, total count, and pagination info
    """
    page = params.get("page", 1)
    limit = params.get("limit", 10)
    host_user_id = params.get("host_user_id")
    upcoming = params.get("upcoming", False)

    offset = (page - 1) * limit

    # Build query conditions
    queryset = Events.objects.filter(deleted_at__isnull=True)

    if host_user_id:
        queryset = queryset.filter(host_user__id=host_user_id)

    if upcoming:
        now = timezone.now()
        queryset = queryset.filter(start_datetime__gte=now)

    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        queryset = queryset.filter(Q(track_id__in=track_ids) | Q(track__isnull=True))

    # Get total count
    total = queryset.count()

    # Fetch only fields used by the admin list. Calling values() with no
    # field list selects every model column, so a newly added unrelated column
    # can break this endpoint before production migrations have caught up.
    raw_items = list(
        queryset.order_by("start_datetime")[offset:offset + limit].values(
            "id",
            "event_name",
            "description",
            "start_datetime",
            "ends_datetime",
            "location",
            "deleted_at",
            "event_image",
            "is_virtual",
            "host_user_id",
            "host_user__first_name",
            "host_user__last_name",
            "host_user__email",
            "location_link",
        )
    )
    items = [_event_to_camel(e) for e in raw_items]

    has_more = offset + len(items) < total

    return {
        "msg": "Events retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


def _event_model_to_camel(event: Events) -> Dict[str, Any]:
    """Convert a Django Events model instance to camelCase dict."""
    host_name = str(event.host_user) if event.host_user_id and event.host_user else None
    host_email = event.host_user.email if event.host_user_id and event.host_user else None

    return {
        "id": event.id,
        "eventName": event.event_name,
        "description": event.description,
        "startDatetime": event.start_datetime.isoformat() if event.start_datetime else None,
        "endsDatetime": event.ends_datetime.isoformat() if event.ends_datetime else None,
        "location": event.location,
        "deletedFlag": event.deleted_at is not None,
        "deletedDatetime": event.deleted_at.isoformat() if event.deleted_at else None,
        "eventImage(img)": event.event_image,
        "isVirtual": event.is_virtual,
        "hostUserId": event.host_user_id,
        "hostName": host_name,
        "hostEmail": host_email,
        "locationLink": event.location_link,
    }


def query_event_by_id(id_str: str) -> EventResponseDict:
    """
    Get a single event by ID.

    Args:
        id_str: Event ID as string

    Returns:
        Dictionary with event data or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}

    try:
        event = Events.objects.select_related("host_user").get(id=event_id, deleted_at__isnull=True)
        return {"msg": "Event retrieved successfully", "data": _event_model_to_camel(event)}
    except Events.DoesNotExist:
        return {"msg": "Event not found", "data": None}


def query_event_targets(id_str: str) -> EventTargetsResponseDict:
    """
    Get target groups, roles, and tracks for an event.
    
    Args:
        id_str: Event ID as string
        
    Returns:
        Dictionary with grouped target IDs
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}
    
    group_rows = EventTargetGroup.objects.filter(event_id=event_id).values_list("group_id", flat=True)
    role_rows = EventTargetRole.objects.filter(event_id=event_id).values_list("role_id", flat=True)
    track_rows = EventTargetTrack.objects.filter(event_id=event_id).values_list("track_id", flat=True)
    
    return {
        "msg": "Event targets retrieved successfully",
        "data": {
            "groupIds": list(group_rows),
            "roleIds": list(role_rows),
            "trackIds": list(track_rows),
        },
    }


@transaction.atomic
def _sync_targets(
    event_id: int,
    group_ids: Optional[List[int]] = None,
    role_ids: Optional[List[int]] = None,
    track_ids: Optional[List[int]] = None,
) -> None:
    """
    Sync event targets with provided IDs.
    
    Args:
        event_id: Event ID
        group_ids: List of group IDs to sync (None to skip)
        role_ids: List of role IDs to sync (None to skip)
        track_ids: List of track IDs to sync (None to skip)
    """
    if group_ids is not None:
        EventTargetGroup.objects.filter(event_id=event_id).delete()
        if group_ids:
            EventTargetGroup.objects.bulk_create([
                EventTargetGroup(event_id=event_id, group_id=gid)
                for gid in group_ids
            ])
    
    if role_ids is not None:
        EventTargetRole.objects.filter(event_id=event_id).delete()
        if role_ids:
            EventTargetRole.objects.bulk_create([
                EventTargetRole(event_id=event_id, role_id=rid)
                for rid in role_ids
            ])
    
    if track_ids is not None:
        EventTargetTrack.objects.filter(event_id=event_id).delete()
        if track_ids:
            EventTargetTrack.objects.bulk_create([
                EventTargetTrack(event_id=event_id, track_id=tid)
                for tid in track_ids
            ])


@transaction.atomic
def create_event(data: Dict[str, Any], requesting_user=None) -> EventResponseDict:
    """
    Create a new event.

    Args:
        data: Event creation data (camelCase from frontend)

    Returns:
        Dictionary with created event or error message
    """
    host_user_id = data.get("hostUserId") or data.get("host_user_id")
    if not host_user_id and requesting_user and requesting_user.is_authenticated:
        host_user_id = requesting_user.id

    # Parse dates
    start_at = data.get("startAt") or data.get("start_at")
    ends_at = data.get("endsAt") or data.get("ends_at")
    if not start_at or not ends_at:
        return {"msg": "startAt and endsAt are required", "data": None}

    try:
        start_datetime = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        ends_datetime = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return {"msg": "startAt and endsAt must be valid ISO datetimes", "data": None}

    if ends_datetime <= start_datetime:
        return {"msg": "endsAt must be after startAt", "data": None}

    event_name = data.get("eventName") or data.get("event_name")
    if not event_name:
        return {"msg": "eventName is required", "data": None}

    location = data.get("location", "").strip() if data.get("location") else None
    is_virtual = data.get("isVirtual") or data.get("is_virtual") or False
    if is_virtual:
        location = None

    event = Events.objects.create(
        event_name=event_name,
        description=data.get("description"),
        location=location,
        is_virtual=is_virtual,
        host_user_id=host_user_id,
        start_datetime=start_datetime,
        ends_datetime=ends_datetime,
        location_link=data.get("location_link") or data.get("locationLink") or None,
    )

    # Sync targets
    _sync_targets(
        event.id,
        data.get("targetGroupIds") or data.get("target_group_ids"),
        data.get("targetRoleIds") or data.get("target_role_ids"),
        data.get("targetTrackIds") or data.get("target_track_ids"),
    )

    return {"msg": "Event created successfully", "data": _event_model_to_camel(event)}


@transaction.atomic
def update_event(id_str: str, data: Dict[str, Any]) -> EventResponseDict:
    """
    Update an existing event.

    Args:
        id_str: Event ID as string
        data: Update data (camelCase from frontend)

    Returns:
        Dictionary with updated event or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}

    try:
        event = Events.objects.get(id=event_id)
    except Events.DoesNotExist:
        return {"msg": "Event not found", "data": None}

    # Prepare updates - accept both camelCase and snake_case
    updates = {}
    host_user_id = data.get("hostUserId") or data.get("host_user_id")
    if host_user_id is not None:
        updates["host_user_id"] = host_user_id
    event_name = data.get("eventName") or data.get("event_name")
    if event_name is not None:
        updates["event_name"] = event_name
    if "description" in data and data["description"] is not None:
        updates["description"] = data["description"]
    if "location" in data and data["location"] is not None:
        updates["location"] = data["location"].strip() if data["location"] else None
    location_link = data.get("location_link") or data.get("locationLink")
    if location_link is not None:
        updates["location_link"] = location_link
    is_virtual = data.get("isVirtual") if "isVirtual" in data else data.get("is_virtual")
    if is_virtual is not None:
        updates["is_virtual"] = is_virtual
    if is_virtual:
        updates["location"] = None
    start_at = data.get("startAt") or data.get("start_at")
    if start_at is not None:
        updates["start_datetime"] = datetime.fromisoformat(
            start_at.replace("Z", "+00:00")
        )
    ends_at = data.get("endsAt") or data.get("ends_at")
    if ends_at is not None:
        updates["ends_datetime"] = datetime.fromisoformat(
            ends_at.replace("Z", "+00:00")
        )

    # Validate date range if both dates are being updated or one is being updated
    start_datetime = updates.get("start_datetime", event.start_datetime)
    ends_datetime = updates.get("ends_datetime", event.ends_datetime)

    if ends_datetime <= start_datetime:
        return {"msg": "endsAt must be after startAt", "data": None}

    # Apply updates
    for key, value in updates.items():
        setattr(event, key, value)
    print("updates:", updates)
    event.save()

    # Sync targets regardless of whether event fields changed
    _sync_targets(
        event_id,
        data.get("targetGroupIds") or data.get("target_group_ids"),
        data.get("targetRoleIds") or data.get("target_role_ids"),
        data.get("targetTrackIds") or data.get("target_track_ids"),
    )

    return {"msg": "Event updated successfully", "data": _event_model_to_camel(event)}


@transaction.atomic
def delete_event(id_str: str) -> EventResponseDict:
    """
    Soft delete an event by setting deleted_at timestamp.
    
    Args:
        id_str: Event ID as string
        
    Returns:
        Dictionary with deleted event or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}
    
    try:
        event = Events.objects.get(id=event_id)
    except Events.DoesNotExist:
        return {"msg": "Event not found", "data": None}
    
    # Delete associated RSVPs
    EventRsvp.objects.filter(event_id=event_id).delete()
    
    # Soft delete the event
    event.deleted_at = timezone.now()
    event.save()
    
    return {"msg": "Event deleted successfully", "data": _event_model_to_camel(event)}


def _rsvp_to_camel(rsvp: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw RSVP values() dict to camelCase for the frontend."""
    return {
        "id": rsvp["id"],
        "eventId": rsvp.get("event_id"),
        "userId": rsvp.get("user_id"),
        "rsvpStatus": rsvp.get("rsvp_status"),
        "respondedAt": rsvp.get("responded_at").isoformat() if rsvp.get("responded_at") else None,
    }


def query_event_rsvps(id_str: str) -> EventResponseDict:
    """
    Get all RSVPs for an event.

    Args:
        id_str: Event ID as string

    Returns:
        Dictionary with RSVPs list or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}

    raw_rsvps = list(
        EventRsvp.objects
        .filter(event_id=event_id)
        .order_by("id")
        .values()
    )
    rsvps = [_rsvp_to_camel(r) for r in raw_rsvps]

    return {"msg": "Event RSVPs retrieved successfully", "data": rsvps}


@transaction.atomic
def create_event_rsvp(id_str: str, data: Dict[str, Any]) -> EventResponseDict:
    """
    Create an RSVP for an event.

    Args:
        id_str: Event ID as string
        data: RSVP creation data (camelCase from frontend)

    Returns:
        Dictionary with created RSVP or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}

    responded_at = timezone.now()

    rsvp = EventRsvp.objects.create(
        event_id=event_id,
        user_id=data.get("userId") or data.get("user_id"),
        rsvp_status=data.get("rsvpStatus") or data.get("rsvp_status"),
        responded_at=responded_at,
    )

    return {
        "msg": "Event RSVP created successfully",
        "data": {
            "id": rsvp.id,
            "eventId": rsvp.event_id,
            "userId": rsvp.user_id,
            "rsvpStatus": rsvp.rsvp_status,
            "respondedAt": rsvp.responded_at.isoformat() if rsvp.responded_at else None,
        },
    }


@transaction.atomic
def update_event_rsvp(rsvp_id_str: str, data: Dict[str, Any]) -> EventResponseDict:
    """
    Update an RSVP.

    Args:
        rsvp_id_str: RSVP ID as string
        data: Update data (camelCase from frontend)

    Returns:
        Dictionary with updated RSVP or error message
    """
    rsvp_id = _to_event_id(rsvp_id_str)
    if not rsvp_id:
        return {"msg": "Invalid RSVP id", "data": None}

    try:
        rsvp = EventRsvp.objects.get(id=rsvp_id)
        rsvp.rsvp_status = data.get("rsvpStatus") or data.get("rsvp_status")
        rsvp.save()
        return {
            "msg": "Event RSVP updated successfully",
            "data": {
                "id": rsvp.id,
                "eventId": rsvp.event_id,
                "userId": rsvp.user_id,
                "rsvpStatus": rsvp.rsvp_status,
                "respondedAt": rsvp.responded_at.isoformat() if rsvp.responded_at else None,
            },
        }
    except EventRsvp.DoesNotExist:
        return {"msg": "Event RSVP not found", "data": None}


# ── Reference data ────────────────────────────────────────────────────────────

def query_groups(requesting_user=None) -> Dict[str, Any]:
    """Get all groups for reference data."""
    qs = Groups.objects.filter(deleted_at__isnull=True)
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        qs = qs.filter(Q(track_id__in=track_ids) | Q(track__isnull=True))
    groups = list(qs.order_by("id").values("id", "group_name"))
    return {
        "msg": "Groups retrieved successfully",
        "data": [{"id": g["id"], "groupName": g["group_name"]} for g in groups],
    }


def query_roles() -> Dict[str, Any]:
    """Get all roles for reference data."""
    roles = list(
        Roles.objects
        .all()
        .order_by("id")
        .values("id", "role_name")
    )
    return {
        "msg": "Roles retrieved successfully",
        "data": [{"id": r["id"], "roleName": r["role_name"]} for r in roles],
    }


def query_tracks(requesting_user=None) -> Dict[str, Any]:
    """Get all tracks for reference data."""
    qs = Tracks.objects.all()
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        qs = qs.filter(id__in=track_ids)
    tracks = list(qs.order_by("id").values("id", "track_name"))
    return {
        "msg": "Tracks retrieved successfully",
        "data": [{"id": t["id"], "trackName": t["track_name"]} for t in tracks],
    }
