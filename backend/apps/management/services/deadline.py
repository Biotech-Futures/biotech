"""The submission deadline and each team's extension, as Management sets
them. Both belong to the submissions app, which gates the student portal;
this is where Management reads and changes them."""
from __future__ import annotations

from apps.grading.services.content import late_by_label


def deadline_status() -> dict | None:
    """The active submission deadline as Management shows it, or None.

    ``is_open`` uses the enforced cutoff (announced time + quiet grace hours),
    matching what the portal actually accepts.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.submissions.models import Deadline

    row = (
        Deadline.objects.filter(is_active=True)
        .select_related("set_by")
        .order_by("-created_at")
        .first()
    )
    if row is None:
        return None
    enforced_until = row.closes_at + timedelta(hours=row.grace_hours)
    set_by = None
    if row.set_by is not None:
        set_by = (
            f"{row.set_by.first_name} {row.set_by.last_name}".strip()
            or row.set_by.email
        )
    return {
        "closes_at": row.closes_at,
        "grace_hours": row.grace_hours,
        "is_open": timezone.now() <= enforced_until,
        "set_by": set_by,
        "created_at": row.created_at,
    }


def submissions_still_open() -> bool:
    """True while any team can still submit — baseline window or extension.

    Guards the release gates: marks and certificates must not go out while
    entries can still change. A missing deadline counts as closed, matching
    the portal (where no configured deadline means nothing is accepted).
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.submissions.models import Deadline, GroupExtension

    now = timezone.now()
    row = Deadline.objects.filter(is_active=True).order_by("-created_at").first()
    if row is not None and now <= row.closes_at + timedelta(hours=row.grace_hours):
        return True
    # An extension keeps that one team's window open past the baseline, and
    # applies even when no baseline deadline exists at all.
    for extended_until, grace_hours in GroupExtension.objects.filter(
        revoked_at__isnull=True
    ).values_list("extended_until", "grace_hours"):
        if now <= extended_until + timedelta(hours=grace_hours):
            return True
    return False


def set_submission_deadline(*, closes_at, grace_hours: int, set_by=None) -> dict:
    """Create a new active deadline row and return the resulting status.

    A new row rather than an edit: old rows are kept as the record of what was
    announced when, and the newest active row is the one in force (matching
    the portal's ``active_deadline`` resolution).
    """
    from apps.submissions.models import Deadline

    Deadline.objects.create(
        closes_at=closes_at, grace_hours=grace_hours, is_active=True, set_by=set_by
    )
    return deadline_status()


def _user_display(user) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or user.email


def _normal_closes_at():
    """The active deadline's announced time, without its grace; None when no
    deadline is set."""
    from apps.submissions.models import Deadline

    row = Deadline.objects.filter(is_active=True).order_by("-created_at").first()
    return row.closes_at if row else None


def _extension_payload(extension, closes_at) -> dict:
    # How far past the normal deadline it runs, its grace aside: "1d 18h".
    # None without a deadline, or when the deadline has moved past it.
    added = (
        late_by_label(extension.extended_until - closes_at)
        if closes_at is not None and extension.extended_until > closes_at
        else None
    )
    return {
        "id": extension.pk,
        "group_id": extension.group_id,
        "group_name": extension.group.group_name,
        "extended_until": extension.extended_until,
        "added": added,
        "grace_hours": extension.grace_hours,
        "reason": extension.reason,
        "granted_at": extension.granted_at,
        "granted_by": _user_display(extension.granted_by),
        "revoked_at": extension.revoked_at,
        "revoked_by": _user_display(extension.revoked_by),
    }


def group_extensions() -> list[dict]:
    """Every per-team deadline extension, revoked ones included (audit trail)."""
    from django.db.models import Case, IntegerField, Value, When

    from apps.submissions.models import GroupExtension

    closes_at = _normal_closes_at()
    return [
        _extension_payload(e, closes_at)
        for e in GroupExtension.objects.select_related("group", "granted_by", "revoked_by")
        .filter(group__deleted_at__isnull=True)
        # Active first (longest-running extension leading — the team with the
        # most extra time), all revoked rows at the end.
        .annotate(
            revoked_rank=Case(
                When(revoked_at__isnull=True, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("revoked_rank", "-extended_until", "group__group_name")
    ]


def set_group_extension(
    *, group_id: int, extended_until, grace_hours: int, reason: str, granted_by
) -> dict:
    """Grant one team's extension.

    Every grant is a fresh row. Any previously active extension is revoked
    first (stamped with the granter) and kept as history, so the full trail
    of grants stays visible.
    """
    from django.utils import timezone

    from apps.submissions.models import GroupExtension

    GroupExtension.objects.filter(group_id=group_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_by=granted_by
    )
    extension = GroupExtension.objects.create(
        group_id=group_id,
        extended_until=extended_until,
        grace_hours=grace_hours,
        reason=reason,
        granted_at=timezone.now(),
        granted_by=granted_by,
    )
    extension = GroupExtension.objects.select_related(
        "group", "granted_by", "revoked_by"
    ).get(pk=extension.pk)
    return _extension_payload(extension, _normal_closes_at())


def remove_group_extension(group_id: int, *, revoked_by=None) -> bool:
    """Revoke a team's extension; True if an active one existed.

    Soft: the row is stamped rather than deleted, so who revoked it (and
    when) stays visible in the extensions list.
    """
    from django.utils import timezone

    from apps.submissions.models import GroupExtension

    updated = GroupExtension.objects.filter(
        group_id=group_id, revoked_at__isnull=True
    ).update(revoked_at=timezone.now(), revoked_by=revoked_by)
    return bool(updated)
