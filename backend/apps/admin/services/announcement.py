from typing import TYPE_CHECKING, TypedDict, Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging
import re

from django.db.models import Q, Exists, OuterRef, F
from django.utils import timezone
from django.db import transaction
from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings
from django.template.loader import render_to_string

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

# Cap on the *body* of any persisted SMTP error message — i.e. the part
# rendered after the exception class name. The full persisted string is
# ``f"{ClassName}: {body}"`` plus an optional ellipsis on truncation, so the
# end-to-end length is bounded by this value plus the longest exception class
# name we expect (well under 60 chars in practice). Tests assert ``< 260`` to
# leave headroom for that prefix.
_MAX_ERROR_BODY_CHARS = 200


def _sanitize_error(exc: BaseException) -> str:
    """
    Render an exception as a one-line, length-bounded string safe to persist
    on a delivery row that admins can read.

    * Strips CR/LF so a malicious server banner can't inject log lines.
    * Truncates the message body to ``_MAX_ERROR_BODY_CHARS`` (the class
      prefix is added on top, so the full string is slightly longer).
    * Always prefixes the exception class so triage doesn't depend on
      provider-specific wording.
    """
    raw_message = str(exc) or ""
    cleaned = raw_message.replace("\r", " ").replace("\n", " ").strip()
    if len(cleaned) > _MAX_ERROR_BODY_CHARS:
        cleaned = cleaned[:_MAX_ERROR_BODY_CHARS].rstrip() + "…"
    return f"{type(exc).__name__}: {cleaned}" if cleaned else type(exc).__name__


# Type definitions
class QueryAnnouncementsInput(TypedDict, total=False):
    page: int
    limit: int
    search: Optional[str]
    archived: Optional[bool]
    sort_by: str
    sort_order: str


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
    return render_to_string("emails/announcement.html", {
        "title": title,
        "excerpt": excerpt,
        "detail_url": detail_url,
        "contact_email": settings.DEFAULT_FROM_EMAIL,
    })


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
    sort_by = params.get("sort_by", "published")
    sort_order = params.get("sort_order", "desc")
    
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
    sort_map = {
        "title": ["title", "id"],
        "audience": ["visibility_scope", "track__track_name", "title", "id"],
        "published": ["published_at", "id"],
        "status": ["archived_at", "published_at", "id"],
    }
    order_by = sort_map.get(sort_by, sort_map["published"])
    if sort_order == "desc":
        order_by = [f"-{field}" if field != "id" else field for field in order_by]

    raw_items = list(
        queryset
        .order_by(*order_by)
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

def _schedule_announcement_email(
    announcement_id: int,
    initiated_by: Optional["UserType"],
) -> None:
    """Defer ``send_announcement_email`` to fire **after** the surrounding
    transaction commits.

    Why this matters: ``create_announcement`` / ``update_announcement`` run
    inside ``@transaction.atomic`` for the row+audience writes. If we called
    the sender inline, the SMTP loop (network I/O, potentially many seconds
    per recipient) would hold the announcement row lock and — worse — any
    ``AnnouncementDelivery`` audit row it created would roll back on a
    subsequent error, even though the emails had already gone out. That is
    *exactly* the audit-trail failure mode the delivery tracking is meant
    to fix.

    ``transaction.on_commit`` also gives us free safety on rollback: if the
    surrounding transaction is rolled back (e.g. a constraint failure later
    in the request), the deferred send is silently dropped, so we never
    notify recipients about an announcement that doesn't actually exist.
    """
    transaction.on_commit(
        lambda: send_announcement_email(
            announcement_id, initiated_by=initiated_by,
        )
    )


def _resolve_author_user_id(
    explicit_id: Optional[int],
    initiated_by: Optional["UserType"],
) -> Optional[int]:
    """Pick the FK for ``Announcement.author_user``.

    The view layer typically passes both ``author_user_id`` (the explicit
    FK) and ``initiated_by`` (the user object that triggered the call). In
    the common case they are the same — ``request.user`` — and we let the
    caller pass either. They are kept as separate inputs because they can
    *legitimately* differ (e.g. a service-account-initiated create on
    behalf of another author, or an impersonation flow). When only
    ``initiated_by`` is supplied we derive the id from it.
    """
    if explicit_id is not None:
        return explicit_id
    return getattr(initiated_by, "id", None)


@transaction.atomic
def create_announcement(
    input_data: CreateAnnouncementInput,
    author_user_id: Optional[int] = None,
    initiated_by: Optional["UserType"] = None,
) -> AnnouncementResponseDict:
    """Create a new announcement.

    ``author_user_id`` and ``initiated_by`` are intentionally distinct
    inputs — see :func:`_resolve_author_user_id` — but in the standard
    request-handler path they come from the same ``request.user`` and the
    caller is free to pass only ``initiated_by``.
    """
    now = timezone.now()

    # Normalise track_ids: accept either track_ids (list) or legacy track_id (single)
    raw_track_ids = input_data.get("track_ids") or []
    if not raw_track_ids and input_data.get("track_id"):
        raw_track_ids = [input_data["track_id"]]
    role_ids = input_data.get("role_ids") or []

    resolved_author_id = _resolve_author_user_id(author_user_id, initiated_by)

    announcement = Announcement.objects.create(
        title=input_data.get("title"),
        body=input_data.get("body"),
        visibility_scope="global",  # will be updated below
        published_at=now,
        author_user_id=resolved_author_id,
        track_id=raw_track_ids[0] if raw_track_ids else None,
    )

    resolved_scope = _sync_audience(announcement.id, raw_track_ids, role_ids)
    announcement.visibility_scope = resolved_scope
    announcement.save(update_fields=["visibility_scope"])

    if input_data.get("send_email"):
        # Deferred to on_commit so SMTP I/O does not run inside this
        # transaction and the AnnouncementDelivery audit row outlives any
        # rollback that happens before commit. See the helper docstring.
        _schedule_announcement_email(announcement.id, initiated_by)

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
        # See ``create_announcement``: deferred to on_commit so the SMTP
        # loop does not run inside the update's atomic block.
        _schedule_announcement_email(announcement_id, initiated_by)

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


def _skipped_send_result(msg: str) -> Dict[str, Any]:
    """Build the ``skipped`` response shape — used both for unknown
    announcements and for empty audiences. ``skipped`` is a wire-only
    status: we never persist an AnnouncementDelivery row for these cases.
    """
    return {
        "msg": msg,
        "deliveryId": None,
        "status": "skipped",
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "failedRecipients": [],
        "sent": 0,
    }


def _deliver_announcement_to_recipients(
    announcement_id: int,
    emails: List[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> Tuple[int, List[Dict[str, str]], Optional[str]]:
    """Run the SMTP loop for a single send attempt.

    Returns ``(succeeded_count, failed_entries, connection_error)`` where
    ``connection_error`` is non-None only when the connection itself never
    opened (i.e. no recipient was actually attempted at the wire).

    This is extracted from :func:`send_announcement_email` so the
    bookkeeping path (delivery row create + finalize) does not share a
    ``finally`` block with the SMTP path. That structurally rules out the
    "``status_value`` referenced before assignment" failure mode that
    earlier versions were one ``return`` away from.
    """
    failed: List[Dict[str, str]] = []
    succeeded: int = 0

    try:
        # ``fail_silently=False`` ensures SMTP / DNS / auth errors raise
        # instead of being swallowed. We catch them ourselves so we can
        # still persist a useful delivery row.
        connection = get_connection(fail_silently=False)
    except Exception as exc:  # extremely unlikely — backend resolution failed
        connection_error = _sanitize_error(exc)
        logger.exception(
            "announcement_email.connection_construct_failed announcement_id=%s",
            announcement_id,
        )
        for addr in emails:
            failed.append({"email": addr, "error": connection_error})
        return 0, failed, connection_error

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
        return 0, failed, connection_error

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
                # ``send()`` returns the number of successfully delivered
                # messages (1 on success). With ``fail_silently=False`` it
                # raises on SMTP errors.
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
                # Reset the SMTP transaction so the connection is not left in
                # a mid-transaction state ("nested MAIL command") for the next
                # recipient after a per-address send failure.
                try:
                    if getattr(connection, "connection", None):
                        connection.connection.rset()
                except Exception:
                    pass
            else:
                if result:
                    succeeded += 1
                else:
                    # Backend reported 0 sent without raising — treat as a
                    # soft failure for tracking.
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
            # ``logger.exception`` here logs the currently-active exception
            # (we are inside ``except Exception:``), which is the close
            # failure — not anything from the surrounding send loop.
            logger.exception(
                "announcement_email.connection_close_failed "
                "announcement_id=%s",
                announcement_id,
            )

    return succeeded, failed, None


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
      * Sends per recipient (each in its own ``EmailMultiAlternatives`` with
        a single-address ``to=[addr]``) so a single bad address doesn't
        poison the batch *and* so recipients are not leaked to each other
        via the ``To:`` header — the previous ``send_mail(recipient_list=...)``
        put every audience email in a single ``To:`` line.
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
                "failedRecipients":  [<email>, ...],   # capped, email-only;
                                                       # persisted shape is
                                                       # objects (see model).
                "sent":              <int>,            # legacy alias for `succeeded`
            }
    """
    row = _fetch_announcement(announcement_id)
    if not row:
        return _skipped_send_result("Announcement not found")

    emails = _resolve_recipient_emails(
        announcement_id, row.get("visibilityScope", "global"),
    )
    if not emails:
        return _skipped_send_result("No recipients found")

    excerpt = _build_excerpt(row.get("body", ""))
    platform_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    detail_url = f"{platform_url}/#/announcements/{announcement_id}"
    subject = f"[BioTech] {row.get('title')}"
    text_body = (
        f"{row.get('title')}\n\n{excerpt}\n\n"
        f"View on the platform: {detail_url}"
    )
    html_body = _render_announcement_email_html(
        row.get("title", ""), excerpt, detail_url,
    )

    # Pessimistic delivery row: created up front as FAILED so a mid-send
    # crash still leaves a triageable audit trail. We finalize it after
    # the SMTP loop returns (or after the catch-all below, if something
    # truly unexpected escapes the helper).
    delivery = AnnouncementDelivery.objects.create(
        announcement_id=announcement_id,
        initiated_by=initiated_by if getattr(initiated_by, "pk", None) else None,
        status=AnnouncementDelivery.Status.FAILED,
        recipient_count=len(emails),
    )

    try:
        succeeded, failed, connection_error = _deliver_announcement_to_recipients(
            announcement_id, emails, subject, text_body, html_body,
        )
    except Exception as exc:  # belt-and-braces — anything truly unexpected
        connection_error = _sanitize_error(exc)
        logger.exception(
            "announcement_email.unexpected_failure announcement_id=%s",
            announcement_id,
        )
        succeeded = 0
        failed = [{"email": addr, "error": connection_error} for addr in emails]

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
    try:
        delivery.save(update_fields=[
            "status", "success_count", "failure_count",
            "failed_recipients", "error_summary", "completed_at",
        ])
    except Exception:
        # The send already happened (or already failed) — losing the audit
        # write to a transient DB blip should not bubble up to callers and
        # erase the response. The row stays at its pessimistic initial
        # state in that case; operators will see the mismatch in logs and
        # we surface the actual outcome to the API.
        logger.exception(
            "announcement_email.delivery_save_failed announcement_id=%s "
            "delivery_id=%s status=%s succeeded=%s failed=%s",
            announcement_id, delivery.pk, status_value, succeeded, failure_count,
        )

    return {
        "msg": msg,
        "deliveryId": delivery.pk,
        "status": status_value,
        "attempted": len(emails),
        "succeeded": succeeded,
        "failed": failure_count,
        # API returns email strings only. The persisted shape on the model
        # is ``[{"email": ..., "error": ...}]`` — see the comment on
        # ``AnnouncementDelivery.failed_recipients``.
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
