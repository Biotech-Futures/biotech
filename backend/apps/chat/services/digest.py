"""Daily "you have unread chat messages" email digest.

Sent from the dedicated ``connect@`` mailbox (not the default transactional
account) so it lives under its own send quota. Driven by an external daily cron
hitting an HMAC-guarded trigger, mirroring the RSVP-reminder pattern
(``apps.events.services.send_due_rsvp_reminders``) — there is no in-process
scheduler in this project.

Unread is derived from the lazily-created ``MessageStatus`` rows: a message with
NO ``read`` status row for a user is unread. Re-notification is throttled per
user via ``ChatDigestState`` (a high-water mark + last-sent timestamp) so a user
is reminded at most once a day, and never again until they read the messages OR
genuinely newer ones arrive.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import Count, Max, Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.chat.models import ChatDigestState, Messages, MessageStatus
from apps.groups.models import GroupMembership
from apps.services.email_branding import attach_inline_logo, brand_context

logger = logging.getLogger(__name__)

_SUPERVISOR = GroupMembership.MembershipRoleChoices.SUPERVISOR
_READ = MessageStatus.StatusChoices.READ


def _min_interval() -> timedelta:
    return timedelta(hours=int(getattr(settings, "UNREAD_DIGEST_MIN_INTERVAL_HOURS", 20)))


def _platform_url() -> str:
    # FE uses hash routing off FRONTEND_BASE_URL and the recipient is logged out,
    # so land them on the app root which routes through login to the chat view.
    # TODO: swap for the exact chat deep-link (e.g. /#/chat) once FE confirms it.
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/#/" if base else base


def _collect_candidates(now):
    """Pass 1 — one query.

    Active mentor/student memberships (supervisors excluded; login-blocked users
    excluded) folded per user, with ``ChatDigestState`` preloaded and
    cadence-blocked users dropped in memory (zero per-user queries). Returns a
    list of ``{user_id, email, first_name, groups: [(gid, name, joined_at)], hwm}``.
    """
    User = get_user_model()
    cutoff = now - _min_interval()

    memberships = (
        GroupMembership.objects.filter(
            left_at__isnull=True,
            group__deleted_at__isnull=True,
        )
        .exclude(membership_role=_SUPERVISOR)
        .exclude(user__account_status__in=User.INACTIVE_LOGIN_STATUSES)
        .values(
            "user_id",
            "group_id",
            "group__group_name",
            "joined_at",
            "user__email",
            "user__first_name",
        )
    )

    by_user: dict = {}
    for m in memberships:
        email = (m["user__email"] or "").strip()
        if not email:
            continue
        entry = by_user.get(m["user_id"])
        if entry is None:
            entry = {
                "user_id": m["user_id"],
                "email": email,
                "first_name": m["user__first_name"] or "",
                "groups": [],
            }
            by_user[m["user_id"]] = entry
        entry["groups"].append((m["group_id"], m["group__group_name"], m["joined_at"]))

    if not by_user:
        return []

    states = {
        s.user_id: s
        for s in ChatDigestState.objects.filter(user_id__in=list(by_user.keys()))
    }

    candidates = []
    for user_id, entry in by_user.items():
        state = states.get(user_id)
        if state and state.last_notified_at and state.last_notified_at >= cutoff:
            continue  # cadence guard — already notified inside the window
        entry["hwm"] = state.last_notified_message_id if state else 0
        candidates.append(entry)
    return candidates


def _compute_unread(candidate):
    """Pass 2 — one query per surviving candidate.

    Returns ``(total, [(group_name, count), ...], new_hwm)`` or ``None`` when the
    user has nothing unread above their high-water mark.
    """
    user_id = candidate["user_id"]
    hwm = candidate["hwm"]

    group_scope = Q()
    for gid, _name, joined_at in candidate["groups"]:
        group_scope |= Q(group_id=gid, sent_at__gte=joined_at)

    rows = (
        Messages.objects.filter(group_scope, deleted_at__isnull=True, id__gt=hwm)
        .exclude(sender_user_id=user_id)
        # BOTH conditions in ONE exclude() -> a single NOT EXISTS(read row for
        # this user). MessageStatus rows are created lazily, so a message with no
        # row at all is unread; a `status != 'read'` filter would wrongly drop it.
        .exclude(statuses__user_id=user_id, statuses__status=_READ)
        .values("group_id")
        .annotate(cnt=Count("id", distinct=True), max_id=Max("id"))
    )

    name_by_group = {gid: name for gid, name, _ in candidate["groups"]}
    per_group = []
    total = 0
    new_hwm = hwm
    for r in rows:
        total += r["cnt"]
        new_hwm = max(new_hwm, r["max_id"] or 0)
        per_group.append((name_by_group.get(r["group_id"]) or "Your group", r["cnt"]))

    if total == 0:
        return None
    per_group.sort(key=lambda t: (-t[1], t[0].lower()))  # most unread first, then name
    return total, per_group, new_hwm


def _claim_user(user_id, new_hwm, cutoff, now) -> bool:
    """Atomic per-user claim. Returns True iff this run won the send slot.

    Concurrent/overlapping runs race on the same conditional UPDATE; exactly one
    updates the row, the others get 0 and skip — so no user is double-sent.
    """
    ChatDigestState.objects.get_or_create(
        user_id=user_id, defaults={"last_notified_message_id": 0}
    )
    claimed = (
        ChatDigestState.objects.filter(user_id=user_id)
        .filter(Q(last_notified_at__isnull=True) | Q(last_notified_at__lt=cutoff))
        .update(last_notified_at=now, last_notified_message_id=new_hwm)
    )
    return bool(claimed)


def _render_and_send(connection, candidate, summary):
    total, per_group, _new_hwm = summary
    ctx = {
        **brand_context(),
        # Digest sends from connect@, so the "add to address book" copy must show
        # connect@, not the default info@ that brand_context() supplies.
        "SENDER_EMAIL": settings.CONNECT_FROM_ADDRESS,
        "First_Name": candidate["first_name"],
        "TOTAL_UNREAD": total,
        "GROUP_COUNT": len(per_group),
        "GROUPS": [{"name": n, "count": c} for n, c in per_group],
        "PLATFORM_URL": _platform_url(),
    }
    plural = "" if total == 1 else "s"
    subject = f"You have {total} unread message{plural} on {ctx['BRAND_CONNECT']}"
    text_body = render_to_string("emails/unread_messages.txt", ctx)
    html_body = render_to_string("emails/unread_messages.html", ctx)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.CONNECT_DEFAULT_FROM_EMAIL,
        to=[candidate["email"]],
        connection=connection,
    )
    msg.attach_alternative(html_body, "text/html")
    attach_inline_logo(msg)
    msg.send(fail_silently=False)


def send_unread_message_digests(*, dry_run=False):
    """Send the daily unread-chat-message digest.

    Returns ``(users_considered, emails_sent, emails_failed)``. ``dry_run``
    reports who would be emailed without claiming state or sending anything.
    """
    now = timezone.now()
    cutoff = now - _min_interval()

    pending = []
    for candidate in _collect_candidates(now):
        summary = _compute_unread(candidate)
        if summary is not None:
            pending.append((candidate, summary))

    considered = len(pending)

    if dry_run:
        for candidate, (total, per_group, _hwm) in pending:
            logger.info(
                "unread_digest.dry_run user=%s total=%s groups=%s",
                candidate["user_id"], total, len(per_group),
            )
        return considered, 0, 0

    if not pending:
        return 0, 0, 0

    try:
        connection = get_connection(
            host=settings.EMAIL_CONNECT_HOST,
            port=settings.EMAIL_CONNECT_PORT,
            username=settings.EMAIL_CONNECT_HOST_USER,
            password=settings.EMAIL_CONNECT_HOST_PASSWORD,
            use_ssl=settings.EMAIL_CONNECT_USE_SSL,
            fail_silently=False,
        )
        connection.open()
    except Exception:
        logger.exception("unread_digest.connection_failed")
        return considered, 0, len(pending)

    sent = 0
    failed = 0
    try:
        for candidate, summary in pending:
            _total, _groups, new_hwm = summary
            # Claim BEFORE sending so an overlapping run can't double-send. A rare
            # post-claim send failure just makes the user wait for the next re-arm
            # (a newer message) — acceptable for a low-stakes reminder.
            if not _claim_user(candidate["user_id"], new_hwm, cutoff, now):
                continue
            try:
                _render_and_send(connection, candidate, summary)
            except Exception as exc:
                failed += 1
                logger.warning(
                    "unread_digest.send_failed user=%s error=%s",
                    candidate["user_id"], exc,
                )
                # Reset the SMTP transaction so a per-address failure doesn't
                # poison the next recipient on the shared connection.
                try:
                    if getattr(connection, "connection", None):
                        connection.connection.rset()
                except Exception:
                    pass
            else:
                sent += 1
    finally:
        try:
            connection.close()
        except Exception:
            logger.exception("unread_digest.connection_close_failed")

    return considered, sent, failed
