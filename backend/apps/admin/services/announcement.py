from typing import TYPE_CHECKING, TypedDict, Optional, List, Dict, Any
from datetime import datetime
import html as html_lib
import logging
import re

from django.db.models import Q, Exists, OuterRef, F
from django.utils import timezone
from django.db import transaction
from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings

from apps.announcements.models import (
    Announcement,
    AnnouncementAudience,
    AnnouncementDelivery,
)
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks
from apps.users.models import User
from apps.admin.scope_utils import get_admin_track_ids

if TYPE_CHECKING:
    # Imported only for typing — avoids a circular import at runtime and lets
    # us annotate the initiator parameter as the concrete user model rather
    # than ``Any``.
    from apps.users.models.user import User as UserType  # noqa: F401

logger = logging.getLogger(__name__)

# Maximum length we keep for any persisted SMTP error message. The raw
# strings can include server banners, internal hostnames, or auth realms;
# we keep enough for an operator to triage and drop the rest.
_MAX_ERROR_MESSAGE_CHARS = 200


def _sanitize_error(exc: BaseException) -> str:
    """
    Render an exception as a one-line, length-bounded string safe to persist
    on a delivery row that admins can read.

    * Strips CR/LF so a malicious server banner can't inject log lines.
    * Truncates the message portion to ``_MAX_ERROR_MESSAGE_CHARS``.
    * Always prefixes the exception class so triage doesn't depend on
      provider-specific wording.
    """
    raw_message = str(exc) or ""
    cleaned = raw_message.replace("\r", " ").replace("\n", " ").strip()
    if len(cleaned) > _MAX_ERROR_MESSAGE_CHARS:
        cleaned = cleaned[:_MAX_ERROR_MESSAGE_CHARS].rstrip() + "…"
    return f"{type(exc).__name__}: {cleaned}" if cleaned else type(exc).__name__


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
    track_ids: Optional[List[int]]
    role_ids: Optional[List[int]]
    send_email: bool


class UpdateAnnouncementInput(TypedDict, total=False):
    title: Optional[str]
    body: Optional[str]
    visibility_scope: Optional[str]
    track_id: Optional[int]
    track_ids: Optional[List[int]]
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
    """Resolve recipient emails based on visibility scope."""
    if visibility_scope == "global":
        users = User.objects.filter(is_active=True).values_list("email", flat=True)
        return list(users)

    audience_rows = AnnouncementAudience.objects.filter(
        announcement_id=announcement_id
    ).values_list("role_id", "track_id")

    if not audience_rows:
        return []

    track_ids = [row[1] for row in audience_rows if row[1] is not None]
    role_ids = [row[0] for row in audience_rows if row[0] is not None]

    emails: set = set()
    now = timezone.now()

    if track_ids:
        track_emails = User.objects.filter(
            is_active=True,
            track_id__in=track_ids,
        ).values_list("email", flat=True)
        emails.update(track_emails)

    if role_ids:
        role_emails = User.objects.filter(
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
        emails.update(role_emails)

    return list(emails)


@transaction.atomic
def _sync_audience(
    announcement_id: int,
    track_ids: Optional[List[int]] = None,
    role_ids: Optional[List[int]] = None,
) -> str:
    """
    Sync audience targeting for an announcement.
    Returns the resolved visibility_scope string.
    """
    AnnouncementAudience.objects.filter(announcement_id=announcement_id).delete()

    track_ids = [t for t in (track_ids or []) if t]
    role_ids = [r for r in (role_ids or []) if r]

    records = []
    for tid in track_ids:
        records.append(AnnouncementAudience(announcement_id=announcement_id, track_id=tid))
    for rid in role_ids:
        records.append(AnnouncementAudience(announcement_id=announcement_id, role_id=rid))

    if records:
        AnnouncementAudience.objects.bulk_create(records)

    if track_ids and role_ids:
        return "track_role_based"
    if track_ids:
        return "track_based"
    if role_ids:
        return "role_based"
    return "global"


# ─── queries ─────────────────────────────────────────────────────────────────

def _fetch_announcement(announcement_id: int) -> Optional[Dict[str, Any]]:
    try:
        announcement = Announcement.objects.select_related(
            "track"
        ).get(id=announcement_id)
    except Announcement.DoesNotExist:
        return None

    audience_rows = list(
        AnnouncementAudience.objects
        .filter(announcement_id=announcement_id)
        .select_related("role")
        .values(
            "id",
            roleId=F("role_id"),
            trackId=F("track_id"),
            roleName=F("role__role_name"),
        )
    )

    return {
        "id": announcement.id,
        "title": announcement.title,
        "body": announcement.body,
        "visibilityScope": announcement.visibility_scope,
        "publishedAt": announcement.published_at.isoformat() if announcement.published_at else None,
        "archivedAt": announcement.archived_at.isoformat() if announcement.archived_at else None,
        "authorUserId": announcement.author_user_id,
        "trackId": announcement.track_id,
        "trackName": announcement.track.track_name if announcement.track else None,
        "audiences": audience_rows,
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
    raw_items = list(
        queryset
        .order_by("-published_at")
        .values(
            "id",
            "title",
            visibilityScope=F("visibility_scope"),
            publishedAt=F("published_at"),
            archivedAt=F("archived_at"),
            authorUserId=F("author_user_id"),
            trackId=F("track_id"),
            trackName=F("track__track_name"),
        )[offset:offset + limit]
    )

    all_ids = [item["id"] for item in raw_items]

    if all_ids:
        audience_rows = list(
            AnnouncementAudience.objects
            .filter(announcement_id__in=all_ids)
            .select_related("role")
            .values(
                "id",
                announcementId=F("announcement_id"),
                roleId=F("role_id"),
                trackId=F("track_id"),
                roleName=F("role__role_name"),
            )
        )
    else:
        audience_rows = []

    audiences_by_announcement: Dict[int, List[Dict]] = {}
    for audience in audience_rows:
        ann_id = audience["announcementId"]
        if ann_id not in audiences_by_announcement:
            audiences_by_announcement[ann_id] = []
        audiences_by_announcement[ann_id].append(audience)

    items = []
    for item in raw_items:
        item["audiences"] = audiences_by_announcement.get(item["id"], [])
        items.append(item)
    
    has_more = offset + len(items) < total
    
    return {
        "msg": "Announcements retrieved successfully",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": has_more,
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
    initiated_by: Optional["UserType"] = None,
) -> AnnouncementResponseDict:
    """Create a new announcement."""
    now = timezone.now()

    # Normalise track_ids: accept either track_ids (list) or legacy track_id (single)
    raw_track_ids = input_data.get("track_ids") or []
    if not raw_track_ids and input_data.get("track_id"):
        raw_track_ids = [input_data["track_id"]]
    role_ids = input_data.get("role_ids") or []

    announcement = Announcement.objects.create(
        title=input_data.get("title"),
        body=input_data.get("body"),
        visibility_scope="global",  # will be updated below
        published_at=now,
        author_user_id=author_user_id,
        track_id=raw_track_ids[0] if raw_track_ids else None,
    )

    resolved_scope = _sync_audience(announcement.id, raw_track_ids, role_ids)
    announcement.visibility_scope = resolved_scope
    announcement.save(update_fields=["visibility_scope"])

    if input_data.get("send_email"):
        send_announcement_email(announcement.id, initiated_by=initiated_by)

    row = _fetch_announcement(announcement.id)
    return {"msg": "Announcement created successfully", "data": row}


@transaction.atomic
def update_announcement(
    announcement_id: int,
    input_data: UpdateAnnouncementInput,
    initiated_by: Optional["UserType"] = None,
) -> AnnouncementResponseDict:
    """Update an existing announcement."""
    existing = _fetch_announcement(announcement_id)
    if not existing:
        return {"msg": "Announcement not found", "data": None}

    try:
        announcement = Announcement.objects.get(id=announcement_id)
    except Announcement.DoesNotExist:
        return {"msg": "Announcement not found", "data": None}

    if "title" in input_data and input_data["title"] is not None:
        announcement.title = input_data["title"]
    if "body" in input_data and input_data["body"] is not None:
        announcement.body = input_data["body"]

    # Determine new track_ids from either track_ids or legacy track_id
    audience_fields = {"track_ids", "track_id", "role_ids"}
    if audience_fields.intersection(input_data.keys()):
        raw_track_ids = input_data.get("track_ids") or []
        if not raw_track_ids and input_data.get("track_id"):
            raw_track_ids = [input_data["track_id"]]
        role_ids = input_data.get("role_ids") or []

        resolved_scope = _sync_audience(announcement_id, raw_track_ids, role_ids)
        announcement.visibility_scope = resolved_scope
        announcement.track_id = raw_track_ids[0] if raw_track_ids else None

    announcement.save()

    if input_data.get("send_email"):
        send_announcement_email(announcement_id, initiated_by=initiated_by)

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
    if existing.get("archivedAt"):
        return {"msg": "Announcement already archived", "data": existing}
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.archived_at = timezone.now()
        announcement.save()
    except Announcement.DoesNotExist:
        return {"msg": "Announcement not found", "data": None}
    
    row = _fetch_announcement(announcement_id)
    return {"msg": "Announcement archived successfully", "data": row}


def send_announcement_email(
    announcement_id: int,
    initiated_by: Optional["UserType"] = None,
) -> Dict[str, Any]:
    """
    Send an announcement to its resolved audience and persist a delivery row.

    Replaces the previous one-shot ``send_mail(..., fail_silently=True)``
    which silently swallowed SMTP errors and lied about success. This version:

      * Opens a single SMTP connection with ``fail_silently=False`` so the
        backend surfaces real errors instead of returning 0/1 booleans.
      * Sends per recipient so a single bad address doesn't poison the batch
        and so we can report which addresses failed.
      * Logs failures via ``logging`` and persists an
        :class:`AnnouncementDelivery` row holding attempted / success / failure
        counts and the (capped) list of failed recipients.

    Args:
        announcement_id: Announcement ID.
        initiated_by:    The user triggering the send (typically
                         ``request.user``). May be ``None`` when called from a
                         background context.

    Returns:
        Dictionary with::

            {
                "msg":               <human readable summary>,
                "deliveryId":        <AnnouncementDelivery PK or None>,
                "status":            "success" | "partial" | "failed" | "skipped",
                "attempted":         <int>,
                "succeeded":         <int>,
                "failed":            <int>,
                "failedRecipients":  [<email>, ...],   # capped
                "sent":              <int>,            # legacy alias for `succeeded`
            }
    """
    row = _fetch_announcement(announcement_id)
    if not row:
        return {
            "msg": "Announcement not found",
            "deliveryId": None,
            "status": "skipped",
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "failedRecipients": [],
            "sent": 0,
        }

    emails = _resolve_recipient_emails(
        announcement_id, row.get("visibilityScope", "global"),
    )

    if not emails:
        return {
            "msg": "No recipients found",
            "deliveryId": None,
            "status": "skipped",
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "failedRecipients": [],
            "sent": 0,
        }

    excerpt = _build_excerpt(row.get("body", ""))
    platform_url = getattr(settings, "PLATFORM_URL", "")
    detail_url = f"{platform_url}/announcements/{announcement_id}"
    subject = f"[BioTech] {row.get('title')}"
    text_body = (
        f"{row.get('title')}\n\n{excerpt}\n\n"
        f"View on the platform: {detail_url}"
    )
    html_body = _render_announcement_email_html(
        row.get("title", ""), excerpt, detail_url,
    )

    delivery = AnnouncementDelivery.objects.create(
        announcement_id=announcement_id,
        initiated_by=initiated_by if getattr(initiated_by, "pk", None) else None,
        status=AnnouncementDelivery.Status.FAILED,  # pessimistic; updated below
        recipient_count=len(emails),
    )

    failed: List[Dict[str, str]] = []
    succeeded: int = 0
    connection_error: Optional[str] = None

    # The outer try/finally guarantees we always persist the final delivery
    # state (status, counts, error summary) even if a future contributor
    # adds an early ``return`` or an unexpected exception escapes the loop.
    # Without this, the pessimistic row created above could be left forever
    # in ``status=FAILED`` with success_count=0.
    try:
        try:
            # ``fail_silently=False`` ensures SMTP / DNS / auth errors raise
            # instead of being swallowed. We catch them ourselves so we can
            # still persist a useful delivery row.
            connection = get_connection(fail_silently=False)
            try:
                connection.open()
            except Exception as exc:  # network / TLS / auth failure
                connection_error = _sanitize_error(exc)
                logger.exception(
                    "announcement_email.connection_failed announcement_id=%s",
                    announcement_id,
                )
                # Mark every recipient as failed since none could be attempted.
                for addr in emails:
                    failed.append({"email": addr, "error": connection_error})
            else:
                try:
                    for addr in emails:
                        message = EmailMultiAlternatives(
                            subject=subject,
                            body=text_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[addr],
                            connection=connection,
                        )
                        message.attach_alternative(html_body, "text/html")
                        try:
                            # ``send()`` returns the number of successfully
                            # delivered messages (1 on success). With
                            # ``fail_silently=False`` it raises on SMTP errors.
                            result = message.send(fail_silently=False)
                        except Exception as exc:
                            failed.append({
                                "email": addr,
                                "error": _sanitize_error(exc),
                            })
                            logger.warning(
                                "announcement_email.send_failed "
                                "announcement_id=%s recipient=%s error=%s",
                                announcement_id, addr, _sanitize_error(exc),
                            )
                        else:
                            if result:
                                succeeded += 1
                            else:
                                # Backend reported 0 sent without raising —
                                # treat as a soft failure for tracking.
                                failed.append({
                                    "email": addr,
                                    "error": "Mail backend reported 0 sent",
                                })
                                logger.warning(
                                    "announcement_email.send_zero "
                                    "announcement_id=%s recipient=%s",
                                    announcement_id, addr,
                                )
                finally:
                    try:
                        connection.close()
                    except Exception:
                        logger.exception(
                            "announcement_email.connection_close_failed "
                            "announcement_id=%s",
                            announcement_id,
                        )
        except Exception as exc:  # belt-and-braces — anything truly unexpected
            connection_error = _sanitize_error(exc)
            logger.exception(
                "announcement_email.unexpected_failure announcement_id=%s",
                announcement_id,
            )
    finally:
        failure_count = len(failed)
        if succeeded == 0:
            status_value = AnnouncementDelivery.Status.FAILED
            msg = (
                "Announcement send failed — no recipients accepted the message"
                if failure_count
                else "Announcement send failed"
            )
        elif failure_count == 0:
            status_value = AnnouncementDelivery.Status.SUCCESS
            msg = "Announcement email sent successfully"
        else:
            status_value = AnnouncementDelivery.Status.PARTIAL
            msg = (
                f"Announcement email partially sent "
                f"({succeeded}/{len(emails)} delivered)"
            )

        capped_failed = failed[: AnnouncementDelivery.FAILED_RECIPIENTS_CAP]
        overflow = failure_count - len(capped_failed)
        error_summary_parts: List[str] = []
        if connection_error:
            error_summary_parts.append(f"connection: {connection_error}")
        if overflow > 0:
            error_summary_parts.append(
                f"+{overflow} more failed recipients omitted from list"
            )
        error_summary = "\n".join(error_summary_parts)

        delivery.status = status_value
        delivery.success_count = succeeded
        delivery.failure_count = failure_count
        delivery.failed_recipients = capped_failed
        delivery.error_summary = error_summary
        delivery.completed_at = timezone.now()
        delivery.save(update_fields=[
            "status", "success_count", "failure_count",
            "failed_recipients", "error_summary", "completed_at",
        ])

    return {
        "msg": msg,
        "deliveryId": delivery.pk,
        "status": status_value,
        "attempted": len(emails),
        "succeeded": succeeded,
        "failed": failure_count,
        "failedRecipients": [item["email"] for item in capped_failed],
        # Legacy alias kept so existing callers / tests that read ``sent``
        # keep working.
        "sent": succeeded,
    }


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
