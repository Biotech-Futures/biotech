from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime
import html as html_lib
import re

from django.db.models import Q, Exists, OuterRef, F
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from apps.announcements.models import Announcement, AnnouncementAudience
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks
from apps.users.models import User
from apps.admin.scope_utils import get_admin_track_ids


# Type definitions
class QueryAnnouncementsInput(TypedDict, total=False):
    page: int
    limit: int
    search: Optional[str]
    archived: Optional[bool]


class CreateAnnouncementInput(TypedDict, total=False):
    title: str
    body: str
    visibility_scope: str
    track_id: Optional[int]
    role_ids: Optional[List[int]]
    send_email: bool


class UpdateAnnouncementInput(TypedDict, total=False):
    title: Optional[str]
    body: Optional[str]
    visibility_scope: Optional[str]
    track_id: Optional[int]
    role_ids: Optional[List[int]]
    send_email: bool


class AnnouncementResponseDict(TypedDict):
    msg: str
    data: Optional[Any]


# ─── helpers ────────────────────────────────────────────────────────────────

def _escape_html(value: str) -> str:
    """Escape HTML special characters."""
    return html_lib.escape(value)


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    # Remove HTML tags
    text = re.sub(r"<[^>]*>", " ", html)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_excerpt(html: str, max_chars: int = 200) -> str:
    """Build plain text excerpt from HTML."""
    text = _strip_html(html)
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


def _render_announcement_email_html(
    title: str,
    excerpt: str,
    detail_url: str,
) -> str:
    """Render announcement email HTML template."""
    return f"""<!doctype html>
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #e3e8f2;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#17324d;color:#ffffff;padding:24px 28px;">
                <div style="font-size:13px;opacity:.82;">BioTech Platform</div>
                <h1 style="margin:8px 0 0;font-size:24px;line-height:32px;font-weight:700;">{_escape_html(title)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;font-size:15px;line-height:24px;">
                <p style="margin:0 0 16px;">{_escape_html(excerpt)}</p>
                <p style="margin:0;"><a href="{_escape_html(detail_url)}" style="color:#17324d;">View full announcement →</a></p>
              </td>
            </tr>
            <tr>
              <td style="border-top:1px solid #e3e8f2;padding:18px 28px;color:#667085;font-size:12px;">
                You are receiving this because you are part of the BioTech platform.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _resolve_recipient_emails(
    announcement_id: int,
    visibility_scope: str,
) -> List[str]:
    """
    Resolve recipient emails based on visibility scope.
    
    Args:
        announcement_id: Announcement ID
        visibility_scope: One of "global", "track_based", "role_based"
        
    Returns:
        List of recipient email addresses
    """
    if visibility_scope == "global":
        users = User.objects.filter(is_active=True).values_list("email", flat=True)
        return list(users)
    
    # Get audience for this announcement
    audience_rows = AnnouncementAudience.objects.filter(
        announcement_id=announcement_id
    ).values_list("role_id", "track_id")
    
    if not audience_rows:
        return []
    
    if visibility_scope == "track_based":
        track_ids = [row[1] for row in audience_rows if row[1] is not None]
        if not track_ids:
            return []
        users = User.objects.filter(
            is_active=True,
            track_id__in=track_ids,
        ).values_list("email", flat=True)
        return list(users)
    
    if visibility_scope == "role_based":
        role_ids = [row[0] for row in audience_rows if row[0] is not None]
        if not role_ids:
            return []
        
        now = timezone.now().isoformat()
        users = User.objects.filter(
            is_active=True,
        ).filter(
            Exists(
                RoleAssignmentHistory.objects.filter(
                    user_id=OuterRef("id"),
                    role_id__in=role_ids,
                ).filter(
                    Q(valid_to__isnull=True) | Q(valid_to__gt=now)
                )
            )
        ).values_list("email", flat=True).distinct()
        
        return list(users)
    
    return []


@transaction.atomic
def _sync_audience(
    announcement_id: int,
    visibility_scope: str,
    track_id: Optional[int] = None,
    role_ids: Optional[List[int]] = None,
) -> None:
    """
    Sync audience targeting for an announcement.
    
    Args:
        announcement_id: Announcement ID
        visibility_scope: One of "global", "track_based", "role_based"
        track_id: Track ID for track-based scope
        role_ids: Role IDs for role-based scope
    """
    AnnouncementAudience.objects.filter(announcement_id=announcement_id).delete()
    
    if visibility_scope == "global":
        return
    
    if visibility_scope == "track_based" and track_id:
        AnnouncementAudience.objects.create(
            announcement_id=announcement_id,
            track_id=track_id,
        )
        return
    
    if visibility_scope == "role_based" and role_ids:
        AnnouncementAudience.objects.bulk_create([
            AnnouncementAudience(
                announcement_id=announcement_id,
                role_id=rid,
            )
            for rid in role_ids
        ])


# ─── queries ─────────────────────────────────────────────────────────────────

def _fetch_announcement(announcement_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a complete announcement with audiences.
    
    Args:
        announcement_id: Announcement ID
        
    Returns:
        Dictionary with announcement data or None
    """
    try:
        announcement = Announcement.objects.select_related(
            "track"
        ).get(id=announcement_id)
    except Announcement.DoesNotExist:
        return None
    
    # Get audiences
    audiences = list(
        AnnouncementAudience.objects
        .filter(announcement_id=announcement_id)
        .select_related("role")
        .values(
            "id",
            "role_id",
            "track_id",
            role_name=F("role__role_name"),
        )
    )
    
    return {
        "id": announcement.id,
        "title": announcement.title,
        "body": announcement.body,
        "visibility_scope": announcement.visibility_scope,
        "published_at": announcement.published_at.isoformat() if announcement.published_at else None,
        "archived_at": announcement.archived_at.isoformat() if announcement.archived_at else None,
        "author_user_id": announcement.author_user_id,
        "track_id": announcement.track_id,
        "track_name": announcement.track.track_name if announcement.track else None,
        "audiences": audiences,
    }


def list_announcements(params: QueryAnnouncementsInput, requesting_user=None) -> Dict[str, Any]:
    """
    List announcements with filtering and pagination.
    
    Args:
        params: Dictionary with page, limit, search, and archived filters
        
    Returns:
        Dictionary with announcements list and pagination info
    """
    page = params.get("page", 1)
    limit = params.get("limit", 10)
    search = params.get("search")
    archived = params.get("archived")
    
    offset = (page - 1) * limit
    
    # Build query conditions
    queryset = Announcement.objects.select_related("track")
    
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(body__icontains=search)
        )
    
    if archived is True:
        queryset = queryset.filter(archived_at__isnull=False)
    else:  # archived is False or None
        queryset = queryset.filter(archived_at__isnull=True)

    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        queryset = queryset.filter(Q(track_id__in=track_ids) | Q(track__isnull=True))

    # Get total count
    total = queryset.count()
    
    # Fetch items
    items = list(
        queryset
        .order_by("-published_at")
        .values(
            "id",
            "title",
            "visibility_scope",
            "published_at",
            "archived_at",
            "author_user_id",
            "track_id",
            track_name=F("track__track_name"),
        )[offset:offset + limit]
    )
    
    # Get all announcement IDs for bulk fetch of audiences
    all_ids = [item["id"] for item in items]
    
    if all_ids:
        audience_rows = list(
            AnnouncementAudience.objects
            .filter(announcement_id__in=all_ids)
            .select_related("role")
            .values(
                "announcement_id",
                "role_id",
                "track_id",
                role_name=F("role__role_name"),
            )
        )
    else:
        audience_rows = []
    
    # Group audiences by announcement
    audiences_by_announcement: Dict[int, List[Dict]] = {}
    for audience in audience_rows:
        ann_id = audience["announcement_id"]
        if ann_id not in audiences_by_announcement:
            audiences_by_announcement[ann_id] = []
        audiences_by_announcement[ann_id].append(audience)
    
    # Attach audiences to items
    for item in items:
        item["audiences"] = audiences_by_announcement.get(item["id"], [])
    
    has_more = offset + len(items) < total
    
    return {
        "msg": "Announcements retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": has_more,
        },
    }


def get_announcement_by_id(announcement_id: int) -> AnnouncementResponseDict:
    """
    Get a single announcement by ID.
    
    Args:
        announcement_id: Announcement ID
        
    Returns:
        Dictionary with announcement or error message
    """
    row = _fetch_announcement(announcement_id)
    if not row:
        return {"msg": "Announcement not found", "data": None}
    return {"msg": "Announcement retrieved successfully", "data": row}


# ─── mutations ───────────────────────────────────────────────────────────────

@transaction.atomic
def create_announcement(
    input_data: CreateAnnouncementInput,
    author_user_id: int,
) -> AnnouncementResponseDict:
    """
    Create a new announcement.
    
    Args:
        input_data: Announcement creation data
        author_user_id: ID of the user creating the announcement
        
    Returns:
        Dictionary with created announcement or error message
    """
    now = timezone.now()
    
    announcement = Announcement.objects.create(
        title=input_data.get("title"),
        body=input_data.get("body"),
        visibility_scope=input_data.get("visibility_scope", "public"),
        published_at=now,
        author_user_id=author_user_id,
        track_id=input_data.get("track_id"),
    )
    
    _sync_audience(
        announcement.id,
        input_data.get("visibility_scope", "public"),
        input_data.get("track_id"),
        input_data.get("role_ids"),
    )
    
    if input_data.get("send_email"):
        send_announcement_email(announcement.id)
    
    row = _fetch_announcement(announcement.id)
    return {"msg": "Announcement created successfully", "data": row}


@transaction.atomic
def update_announcement(
    announcement_id: int,
    input_data: UpdateAnnouncementInput,
) -> AnnouncementResponseDict:
    """
    Update an existing announcement.
    
    Args:
        announcement_id: Announcement ID
        input_data: Update data
        
    Returns:
        Dictionary with updated announcement or error message
    """
    existing = _fetch_announcement(announcement_id)
    if not existing:
        return {"msg": "Announcement not found", "data": None}
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
    except Announcement.DoesNotExist:
        return {"msg": "Announcement not found", "data": None}
    
    # Apply updates
    if "title" in input_data and input_data["title"] is not None:
        announcement.title = input_data["title"]
    if "body" in input_data and input_data["body"] is not None:
        announcement.body = input_data["body"]
    if "visibility_scope" in input_data and input_data["visibility_scope"] is not None:
        announcement.visibility_scope = input_data["visibility_scope"]
    if "track_id" in input_data and input_data["track_id"] is not None:
        announcement.track_id = input_data["track_id"]
    
    if any(k in input_data for k in ["title", "body", "visibility_scope", "track_id"]):
        announcement.save()
    
    # Sync audience if relevant fields changed
    next_scope = input_data.get("visibility_scope", existing.get("visibility_scope"))
    next_track_id = input_data.get("track_id", existing.get("track_id"))
    
    if any(k in input_data for k in ["visibility_scope", "track_id", "role_ids"]):
        _sync_audience(
            announcement_id,
            next_scope,
            next_track_id,
            input_data.get("role_ids"),
        )
    
    if input_data.get("send_email"):
        send_announcement_email(announcement_id)
    
    row = _fetch_announcement(announcement_id)
    return {"msg": "Announcement updated successfully", "data": row}


@transaction.atomic
def archive_announcement(announcement_id: int) -> AnnouncementResponseDict:
    """
    Archive an announcement.
    
    Args:
        announcement_id: Announcement ID
        
    Returns:
        Dictionary with archived announcement or error message
    """
    existing = _fetch_announcement(announcement_id)
    if not existing:
        return {"msg": "Announcement not found", "data": None}
    if existing.get("archived_at"):
        return {"msg": "Announcement already archived", "data": existing}
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.archived_at = timezone.now()
        announcement.save()
    except Announcement.DoesNotExist:
        return {"msg": "Announcement not found", "data": None}
    
    row = _fetch_announcement(announcement_id)
    return {"msg": "Announcement archived successfully", "data": row}


def send_announcement_email(announcement_id: int) -> Dict[str, Any]:
    """
    Send announcement via email to recipients.
    
    Args:
        announcement_id: Announcement ID
        
    Returns:
        Dictionary with send status and count
    """
    row = _fetch_announcement(announcement_id)
    if not row:
        return {"msg": "Announcement not found", "sent": 0}
    
    # Note: Original is async, but send_mail is synchronous in Django
    # If you need async, use Celery or similar
    emails = _resolve_recipient_emails(announcement_id, row.get("visibility_scope", "public"))
    
    if not emails:
        return {"msg": "No recipients found", "sent": 0}
    
    excerpt = _build_excerpt(row.get("body", ""))
    
    platform_url = getattr(settings, "PLATFORM_URL", "")
    detail_url = f"{platform_url}/announcements/{announcement_id}"
    
    send_mail(
        subject=f"[BioTech] {row.get('title')}",
        message=f"{row.get('title')}\n\n{excerpt}\n\nView on the platform: {detail_url}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@biotech.com"),
        recipient_list=emails,
        html_message=_render_announcement_email_html(
            row.get("title", ""),
            excerpt,
            detail_url,
        ),
        fail_silently=True,
    )
    
    return {"msg": "Email sent successfully", "sent": len(emails)}


def list_announcement_tracks(requesting_user=None) -> Dict[str, Any]:
    """Get all tracks for announcement reference data."""
    qs = Tracks.objects.all()
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        qs = qs.filter(id__in=track_ids)
    tracks = list(qs.order_by("track_name").values("id", name=F("track_name")))
    return {"msg": "Tracks retrieved successfully", "data": tracks}


def list_announcement_roles() -> Dict[str, Any]:
    """Get all roles for announcement reference data."""
    roles = list(
        Roles.objects
        .all()
        .order_by("role_name")
        .values("id", name=F("role_name"))
    )
    return {"msg": "Roles retrieved successfully", "data": roles}