from typing import TypedDict, Optional, List
from datetime import datetime

from django.db.models import Q, F, Exists, OuterRef, Value, CharField, BooleanField, Count
from django.db.models.functions import Concat
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.chat.models import Messages
from apps.chat.serializers import is_admin_actor
from apps.chat.views import _broadcast, serialize_message_for_broadcast
from apps.users.models import User, MentorProfile, StudentProfile
from apps.admin.scope_utils import get_admin_track_ids


# Type definitions
class GroupMemberDict(TypedDict):
    id: str
    name: str
    email: str
    role: str  # "student" or "mentor"
    membershipId: Optional[int]


class GroupSenderDict(TypedDict):
    id: str
    name: str
    email: str
    role: Optional[str]  # "student", "mentor", or None


class GroupMessageDict(TypedDict):
    id: str
    group_id: str
    sender: GroupSenderDict
    text: str
    sent_at: str
    edited_at: Optional[str]


class GroupDict(TypedDict):
    id: str
    name: str
    track: str
    members: List[GroupMemberDict]
    mentor: Optional[GroupMemberDict]
    createdAt: str
    updatedAt: str
    deletedAt: Optional[str]


class GroupBaseRow(TypedDict):
    id: int
    name: str
    track: str
    created_at: datetime
    deleted_at: Optional[datetime]


class PaginatedResponse(TypedDict):
    items: List
    total: int
    page: int
    limit: int
    has_more: bool


def _get_member_role(user_id: int) -> Optional[str]:
    """Determine if a user is a mentor or student."""
    if MentorProfile.objects.filter(user_id=user_id).exists():
        return "mentor"
    if StudentProfile.objects.filter(user_id=user_id).exists():
        return "student"
    return None


def _build_groups(base_rows: List[GroupBaseRow]) -> List[GroupDict]:
    """
    Build complete group objects with members and mentor information.
    
    Args:
        base_rows: List of basic group information
        
    Returns:
        List of complete Group dictionaries
    """
    if not base_rows:
        return []
    
    group_ids = [row["id"] for row in base_rows]
    
    # Fetch all active members for these groups
    members_qs = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True
        )
        .select_related("user", "user__mentorprofile", "user__studentprofile")
        .order_by("group_id", "id")
    )
    
    # Organize members by group and role
    members_by_group_id = {}
    mentor_by_group_id = {}
    
    for membership in members_qs:
        user = membership.user
        role = _get_member_role(user.id)
        
        if not role:
            continue
        
        member = {
            "id": str(user.id),
            "name": f"{user.first_name} {user.last_name}".strip(),
            "email": user.email,
            "role": role,
            "membershipId": membership.id,
        }
        
        if role == "mentor":
            mentor_by_group_id[membership.group_id] = member
        else:
            if membership.group_id not in members_by_group_id:
                members_by_group_id[membership.group_id] = []
            members_by_group_id[membership.group_id].append(member)
    
    # Build complete group objects
    result = []
    for row in base_rows:
        group_id = row["id"]
        result.append({
            "id": str(group_id),
            "name": row["name"],
            "track": row["track"],
            "members": members_by_group_id.get(group_id, []),
            "mentor": mentor_by_group_id.get(group_id, None),
            "createdAt": row["created_at"].isoformat(),
            "updatedAt": row["created_at"].isoformat(),
            "deletedAt": row["deleted_at"].isoformat() if row.get("deleted_at") else None,
        })
    
    return result


def _build_group_where(
    search_name: Optional[str] = None,
    search_group: Optional[str] = None,
    track: Optional[str] = None,
    mentor_status: Optional[str] = None,
    deleted: bool = False,
) -> Q:
    """
    Build query conditions for filtering groups.
    
    Args:
        search_name: Search by member name
        search_group: Search by group name
        track: Filter by track name
        mentor_status: Filter by mentor status ("matched" or "unmatched")
        
    Returns:
        Q object with combined conditions
    """
    conditions = [Q(deleted_at__isnull=not deleted)]
    
    if track:
        conditions.append(Q(track__track_name=track))
    
    if search_group:
        conditions.append(Q(group_name__icontains=search_group))
    
    # Filter by mentor status
    if mentor_status:
        mentor_membership_exists = Exists(
            GroupMembership.objects.filter(
                group_id=OuterRef("id"),
                membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
                left_at__isnull=True,
            )
        )
        
        if mentor_status == "matched":
            conditions.append(mentor_membership_exists)
        elif mentor_status == "unmatched":
            conditions.append(~mentor_membership_exists)
    
    # Filter by member name
    if search_name:
        search_pattern = f"%{search_name}%"
        matching_member_exists = Exists(
            GroupMembership.objects.filter(
                group_id=OuterRef("id"),
                left_at__isnull=True,
            ).select_related("user").filter(
                Q(user__first_name__icontains=search_name) |
                Q(user__last_name__icontains=search_name) |
                Q(user__email__icontains=search_name)
            )
        )
        conditions.append(matching_member_exists)
    
    return Q(*conditions)


def _fetch_group_base_by_id(group_id: int, *, include_deleted: bool = False) -> Optional[GroupBaseRow]:
    """
    Fetch basic group information by ID.
    
    Args:
        group_id: The group ID
        
    Returns:
        GroupBaseRow if found, None otherwise
    """
    try:
        filters = {"id": group_id}
        if not include_deleted:
            filters["deleted_at__isnull"] = True
        group = Groups.objects.select_related("track").get(**filters)
        return {
            "id": group.id,
            "name": group.group_name,
            "track": group.track.track_name,
            "created_at": group.created_at,
            "deleted_at": group.deleted_at,
        }
    except Groups.DoesNotExist:
        return None


def _admin_can_access_group(group: Groups, requesting_user=None) -> bool:
    if requesting_user is None:
        return True
    track_ids = get_admin_track_ids(requesting_user)
    return track_ids is None or group.track_id in track_ids


def query_groups(
    page: int = 1,
    limit: int = 10,
    search_name: Optional[str] = None,
    search_group: Optional[str] = None,
    track: Optional[str] = None,
    mentor_status: Optional[str] = None,
    requesting_user=None,
    deleted: bool = False,
) -> dict:
    """
    Query groups with pagination and filtering.
    
    Args:
        page: Page number (1-indexed)
        limit: Items per page
        search_name: Search by member name
        search_group: Search by group name
        track: Filter by track name
        mentor_status: Filter by mentor status
        
    Returns:
        Dictionary with groups, pagination, and metadata
    """
    offset = (page - 1) * limit
    where = _build_group_where(search_name, search_group, track, mentor_status, deleted)

    track_ids = get_admin_track_ids(requesting_user) if requesting_user is not None else None
    if track_ids is not None:
        where = where & (Q(track_id__in=track_ids) | Q(track__isnull=True))

    # Get total count
    total = Groups.objects.filter(where).count()
    
    # Fetch paginated base rows
    base_rows = list(
        Groups.objects
        .select_related("track")
        .filter(where)
        .order_by("-created_at", "-id")
        .values(
            "id",
            "group_name",
            "track__track_name",
            "created_at",
            "deleted_at",
        )[offset:offset + limit]
    )
    
    # Convert to GroupBaseRow format
    formatted_rows = [
        {
            "id": row["id"],
            "name": row["group_name"],
            "track": row["track__track_name"],
            "created_at": row["created_at"],
            "deleted_at": row["deleted_at"],
        }
        for row in base_rows
    ]
    
    # Build complete groups
    items = _build_groups(formatted_rows)
    has_more = offset + len(items) < total
    
    return {
        "msg": "Groups retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


def query_group_by_id(group_id: str) -> dict:
    """
    Get a single group by ID.
    
    Args:
        group_id: The group ID as string
        
    Returns:
        Dictionary with group data or error message
    """
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}
    
    base_row = _fetch_group_base_by_id(gid)
    if not base_row:
        return {"msg": "Group not found", "data": None}
    
    groups = _build_groups([base_row])
    return {
        "msg": "Group retrieved successfully",
        "data": groups[0] if groups else None,
    }


@transaction.atomic
def delete_group(group_id: str, requesting_user=None) -> dict:
    """Soft-delete an active group from adminweb."""
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}

    try:
        group = Groups.objects.select_related("track").get(
            id=gid,
            deleted_at__isnull=True,
        )
    except Groups.DoesNotExist:
        return {"msg": "Group not found", "data": None}

    if not _admin_can_access_group(group, requesting_user):
        return {"msg": "Group not found", "data": None}

    group.deleted_at = timezone.now()
    group.save(update_fields=["deleted_at"])

    return {
        "msg": "Group deleted successfully",
        "data": {
            "id": str(group.id),
            "deletedAt": group.deleted_at.isoformat(),
        },
    }


@transaction.atomic
def restore_group(group_id: str, requesting_user=None) -> dict:
    """Restore a soft-deleted group for the admin recovery table."""
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}

    try:
        group = Groups.objects.select_related("track").get(
            id=gid,
            deleted_at__isnull=False,
        )
    except Groups.DoesNotExist:
        return {"msg": "Group not found", "data": None}

    if not _admin_can_access_group(group, requesting_user):
        return {"msg": "Group not found", "data": None}

    duplicate_exists = Groups.objects.filter(
        track=group.track,
        group_name=group.group_name,
        deleted_at__isnull=True,
    ).exclude(id=group.id).exists()
    if duplicate_exists:
        return {
            "msg": "An active group with this name already exists on the same track",
            "data": None,
        }

    group.restore()
    base_row = _fetch_group_base_by_id(gid)
    groups = _build_groups([base_row]) if base_row else []
    return {
        "msg": "Group restored successfully",
        "data": groups[0] if groups else None,
    }


def query_group_messages(
    group_id: str,
    page: int = 1,
    limit: int = 50,
    deleted: bool = False,
) -> dict:
    """
    Query messages for a group with pagination.
    
    Args:
        group_id: The group ID as string
        page: Page number (1-indexed)
        limit: Items per page
        
    Returns:
        Dictionary with messages, pagination, and metadata
    """
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}
    
    # Verify group exists
    if not _fetch_group_base_by_id(gid):
        return {"msg": "Group not found", "data": None}
    
    offset = (page - 1) * limit
    
    # Get total count
    deleted_filter = {"deleted_at__isnull": not deleted}
    total = Messages.objects.filter(group_id=gid, **deleted_filter).count()
    
    # Fetch paginated messages
    message_records = (
        Messages.objects
        .filter(
            group_id=gid,
            **deleted_filter,
        )
        .select_related(
            "sender_user",
            "sender_user__mentorprofile",
            "sender_user__studentprofile",
            "deleted_by",
        )
        .prefetch_related("attachments", "gif")
        .order_by("sent_at", "id")[offset:offset + limit]
    )

    items = []
    for msg in message_records:
        sender_user = msg.sender_user
        role = _get_member_role(sender_user.id)

        attachments = []
        for att in msg.attachments.all():
            attachments.append({
                "id": att.id,
                "filename": att.attachment_filename,
                "mime_type": att.attachment_mime_type,
                "size": att.attachment_size,
                "download_url": (
                    f"/api/v1/chat/groups/{gid}/messages/{msg.id}"
                    f"/attachments/{att.id}/download"
                ),
            })

        gif = None
        try:
            g = msg.gif
            gif = {
                "gif_url": g.gif_url,
                "preview_url": g.preview_url,
                "title": g.title,
            }
        except Exception:
            pass

        deleted_by = msg.deleted_by
        deleted_by_is_admin = is_admin_actor(deleted_by)

        items.append({
            "id": str(msg.id),
            "group_id": str(msg.group_id),
            "sender": {
                "id": str(sender_user.id),
                "name": f"{sender_user.first_name} {sender_user.last_name}".strip(),
                "email": sender_user.email,
                "role": role,
            },
            "message_type": msg.message_type,
            "text": msg.message_text if not msg.deleted_at else "",
            "attachments": attachments if not msg.deleted_at else [],
            "gif": gif,
            "sent_at": msg.sent_at.isoformat(),
            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
            "deleted_at": msg.deleted_at.isoformat() if msg.deleted_at else None,
            "deleted_by": str(msg.deleted_by_id) if msg.deleted_by_id else None,
            "deleted_by_name": (
                "Admin"
                if deleted_by_is_admin
                else (
                    deleted_by.get_full_name() or deleted_by.get_username()
                    if deleted_by
                    else ""
                )
            ),
            "deleted_by_is_admin": deleted_by_is_admin,
        })
    
    has_more = offset + len(items) < total
    
    return {
        "msg": "Group messages retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


@transaction.atomic
def update_group(group_id: str, name: Optional[str] = None, track: Optional[str] = None) -> dict:
    """
    Update group information.
    
    Args:
        group_id: The group ID as string
        name: New group name
        track: New track name
        
    Returns:
        Dictionary with updated group data or error message
    """
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}
    
    try:
        group = Groups.objects.get(id=gid, deleted_at__isnull=True)
    except Groups.DoesNotExist:
        return {"msg": "Group not found", "data": None}
    
    updates = {}
    
    if name is not None:
        updates["group_name"] = name
    
    if track is not None:
        try:
            track_obj = Tracks.objects.get(track_name=track)
            updates["track"] = track_obj
        except Tracks.DoesNotExist:
            return {"msg": f'Track "{track}" not found', "data": None}
    
    if updates:
        next_name = updates.get("group_name", group.group_name)
        next_track = updates.get("track", group.track)
        if Groups.objects.filter(
            track=next_track,
            group_name=next_name,
            deleted_at__isnull=True,
        ).exclude(id=group.id).exists():
            return {
                "msg": "An active group with this name already exists on the same track",
                "data": None,
            }
        for key, value in updates.items():
            setattr(group, key, value)
        group.save()
    
    # Return updated group
    base_row = _fetch_group_base_by_id(gid)
    if not base_row:
        return {"msg": "Group not found", "data": None}
    
    groups = _build_groups([base_row])
    return {
        "msg": "Group updated successfully",
        "data": groups[0] if groups else None,
    }


@transaction.atomic
def remove_group_member(group_id: str, user_id: int) -> dict:
    """
    Remove a student member from a group.
    
    Args:
        group_id: The group ID as string
        user_id: The user ID to remove
        
    Returns:
        Dictionary with updated group data or error message
    """
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}
    
    if not _fetch_group_base_by_id(gid):
        return {"msg": "Group not found", "data": None}
    
    # Find and verify membership (must be a student)
    try:
        membership = GroupMembership.objects.get(
            group_id=gid,
            user_id=user_id,
            left_at__isnull=True,
        )
        
        # Verify user is a student
        if not StudentProfile.objects.filter(user_id=user_id).exists():
            return {"msg": "Group member not found", "data": None}
        
    except GroupMembership.DoesNotExist:
        return {"msg": "Group member not found", "data": None}
    
    # Delete the membership
    membership.delete()
    
    # Return updated group
    base_row = _fetch_group_base_by_id(gid)
    if not base_row:
        return {"msg": "Group not found", "data": None}
    
    groups = _build_groups([base_row])
    return {
        "msg": "Group member removed successfully",
        "data": groups[0] if groups else None,
    }


@transaction.atomic
def remove_group_message(group_id: str, message_id: int, actor=None) -> dict:
    """
    Soft-delete a message from a group.
    
    Args:
        group_id: The group ID as string
        message_id: The message ID to delete
        
    Returns:
        Dictionary with deleted message info or error message
    """
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}
    
    if not _fetch_group_base_by_id(gid):
        return {"msg": "Group not found", "data": None}
    
    try:
        message = Messages.objects.get(
            id=message_id,
            group_id=gid,
            deleted_at__isnull=True,
        )
    except Messages.DoesNotExist:
        return {"msg": "Group message not found", "data": None}
    
    message.soft_delete(deleted_by=actor)
    message.refresh_from_db()
    _broadcast(
        message.group_id,
        "message.deleted",
        serialize_message_for_broadcast(message),
    )
    
    return {
        "msg": "Group message removed successfully",
        "data": {
            "id": str(message.id),
            "group_id": str(message.group_id),
        },
    }


@transaction.atomic
def restore_group_message(group_id: str, message_id: int, actor=None) -> dict:
    try:
        gid = int(group_id)
    except (ValueError, TypeError):
        return {"msg": "Group not found", "data": None}

    if not _fetch_group_base_by_id(gid):
        return {"msg": "Group not found", "data": None}

    try:
        message = Messages.objects.select_related("group").get(
            id=message_id,
            group_id=gid,
            deleted_at__isnull=False,
        )
    except Messages.DoesNotExist:
        return {"msg": "Group message not found", "data": None}

    message.restore()
    message.refresh_from_db()
    _broadcast(
        message.group_id,
        "message.restored",
        serialize_message_for_broadcast(message),
    )

    return {
        "msg": "Group message restored successfully",
        "data": {
            "id": str(message.id),
            "group_id": str(message.group_id),
        },
    }
