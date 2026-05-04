from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime

from django.db.models import Q, F, Count, Exists, OuterRef, query
from django.utils import timezone
from django.db import transaction

from apps.events.models import Events, EventRsvp, EventTargetGroup, EventTargetRole, EventTargetTrack
from apps.groups.models import Groups, Tracks
from apps.resources.models import Roles
from apps.users.models import User


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


def query_events(params: QueryEventsInput) -> PaginatedEventResponse:
    """
    Query events with pagination and filtering.
    
    Args:
        params: Dictionary with page, limit, host_user_id, and upcoming filters
        
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
    
    # Get total count
    total = queryset.count()
    
    # Fetch paginated items
    items = list(queryset.order_by("start_datetime")[offset:offset + limit].values())
    
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
        event = Events.objects.get(id=event_id, deleted_at__isnull=True)
        return {"msg": "Event retrieved successfully", "data": event}
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
            "group_ids": list(group_rows),
            "role_ids": list(role_rows),
            "track_ids": list(track_rows),
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
def create_event(data: CreateEventInput) -> EventResponseDict:
    """
    Create a new event.
    
    Args:
        data: Event creation data
        
    Returns:
        Dictionary with created event or error message
    """
    if not data.get("host_user_id"):
        raise ValueError("host_user_id is required")
    
    # Parse dates
    start_datetime = datetime.fromisoformat(data["start_at"].replace("Z", "+00:00"))
    ends_datetime = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
    
    location = data.get("location", "").strip() if data.get("location") else None
    
    event = Events.objects.create(
        event_name=data.get("event_name"),
        description=data.get("description"),
        location=location,
        is_virtual=data.get("is_virtual", False),
        host_user_id=data.get("host_user_id"),
        start_datetime=start_datetime,
        ends_datetime=ends_datetime,
    )
    
    # Sync targets
    _sync_targets(
        event.id,
        data.get("target_group_ids"),
        data.get("target_role_ids"),
        data.get("target_track_ids"),
    )
    
    return {"msg": "Event created successfully", "data": event}


@transaction.atomic
def update_event(id_str: str, data: UpdateEventInput) -> EventResponseDict:
    """
    Update an existing event.
    
    Args:
        id_str: Event ID as string
        data: Event update data
        
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
    
    # Prepare updates
    updates = {}
    if "host_user_id" in data and data["host_user_id"] is not None:
        updates["host_user_id"] = data["host_user_id"]
    if "event_name" in data and data["event_name"] is not None:
        updates["event_name"] = data["event_name"]
    if "description" in data and data["description"] is not None:
        updates["description"] = data["description"]
    if "location" in data and data["location"] is not None:
        location = data["location"].strip() if data["location"] else None
        updates["location"] = location
    if "is_virtual" in data and data["is_virtual"] is not None:
        updates["is_virtual"] = data["is_virtual"]
    if "start_at" in data and data["start_at"] is not None:
        updates["start_datetime"] = datetime.fromisoformat(
            data["start_at"].replace("Z", "+00:00")
        )
    if "ends_at" in data and data["ends_at"] is not None:
        updates["ends_datetime"] = datetime.fromisoformat(
            data["ends_at"].replace("Z", "+00:00")
        )
    
    # Validate date range if both dates are being updated or one is being updated
    start_datetime = updates.get("start_datetime", event.start_datetime)
    ends_datetime = updates.get("ends_datetime", event.ends_datetime)
    
    if ends_datetime <= start_datetime:
        return {"msg": "endsAt must be after startAt", "data": None}
    
    # Apply updates
    for key, value in updates.items():
        setattr(event, key, value)
    event.save()
    
    # Sync targets regardless of whether event fields changed
    _sync_targets(
        event_id,
        data.get("target_group_ids"),
        data.get("target_role_ids"),
        data.get("target_track_ids"),
    )
    
    return {"msg": "Event updated successfully", "data": event}


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
    
    return {"msg": "Event deleted successfully", "data": event}


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
    
    rsvps = list(
        EventRsvp.objects
        .filter(event_id=event_id)
        .order_by("id")
        .values()
    )
    
    return {"msg": "Event RSVPs retrieved successfully", "data": rsvps}


@transaction.atomic
def create_event_rsvp(id_str: str, data: CreateEventRsvpInput) -> EventResponseDict:
    """
    Create an RSVP for an event.
    
    Args:
        id_str: Event ID as string
        data: RSVP creation data with user_id and rsvp_status
        
    Returns:
        Dictionary with created RSVP or error message
    """
    event_id = _to_event_id(id_str)
    if not event_id:
        return {"msg": "Invalid event id", "data": None}
    
    # Note: The original uses Date.now() - 600000 (10 minutes ago)
    # This seems unusual; adjust based on actual requirements
    responded_at = timezone.now()
    
    rsvp = EventRsvp.objects.create(
        event_id=event_id,
        user_id=data.get("user_id"),
        rsvp_status=data.get("rsvp_status"),
        responded_at=responded_at,
    )
    
    return {"msg": "Event RSVP created successfully", "data": rsvp}


@transaction.atomic
def update_event_rsvp(rsvp_id_str: str, data: UpdateEventRsvpInput) -> EventResponseDict:
    """
    Update an RSVP.
    
    Args:
        rsvp_id_str: RSVP ID as string
        data: Update data with rsvp_status
        
    Returns:
        Dictionary with updated RSVP or error message
    """
    rsvp_id = _to_event_id(rsvp_id_str)
    if not rsvp_id:
        return {"msg": "Invalid RSVP id", "data": None}
    
    try:
        rsvp = EventRsvp.objects.get(id=rsvp_id)
        rsvp.rsvp_status = data.get("rsvp_status")
        rsvp.save()
        return {"msg": "Event RSVP updated successfully", "data": rsvp}
    except EventRsvp.DoesNotExist:
        return {"msg": "Event RSVP not found", "data": None}


# ── Reference data ────────────────────────────────────────────────────────────

def query_groups() -> Dict[str, Any]:
    """Get all groups for reference data."""
    groups = list(
        Groups.objects
        .filter(deleted_at__isnull=True)
        .order_by("id")
        .values("id", "group_name")
    )
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


def query_tracks() -> Dict[str, Any]:
    """Get all tracks for reference data."""
    tracks = list(
        Tracks.objects
        .all()
        .order_by("id")
        .values("id", "track_name")
    )
    return {
        "msg": "Tracks retrieved successfully",
        "data": [{"id": t["id"], "trackName": t["track_name"]} for t in tracks],
    }