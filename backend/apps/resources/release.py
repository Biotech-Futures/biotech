"""Releasing resources (the Resources page, for admins): when students, mentors and
supervisors get a resource. Shown, it's theirs now; hidden, it's theirs from
its release date (the start of that day, Sydney time), or not at all without
one. Admins always have it.

Each year's first release is kept (ResourceRelease), so the next year's table
can sort by it (Last released). A release date still to come is kept as that
year's release until it comes, moved if the date changes, and dropped if it's
cleared or the resource is shown first."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .models import ResourceRelease

SYDNEY = ZoneInfo("Australia/Sydney")


def sydney_today(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(SYDNEY).date()


def release_moment(day: date) -> datetime:
    """When a resource released on ``day`` appears: the start of it, Sydney time."""
    return datetime.combine(day, time.min, tzinfo=SYDNEY)


def released_q(now: datetime | None = None) -> Q:
    """The resources students, mentors and supervisors have now."""
    return Q(shown=True) | Q(release_on__lte=sydney_today(now))


def is_released(resource, now: datetime | None = None) -> bool:
    return resource.shown or (resource.release_on is not None and resource.release_on <= sydney_today(now))


def last_released(resource_ids, now: datetime | None = None) -> dict:
    """Each resource's release last year (Sydney time), by its id."""
    year = sydney_today(now).year - 1
    return dict(
        ResourceRelease.objects.filter(resource_id__in=list(resource_ids), year=year).values_list(
            "resource_id", "released_at",
        )
    )


def _record(resource, when: datetime, now: datetime) -> None:
    """The year's release (the year of ``when``, Sydney time): the first one
    kept, one still to come moved to ``when``."""
    year = when.astimezone(SYDNEY).year
    row = ResourceRelease.objects.filter(resource=resource, year=year).first()
    if row is None:
        ResourceRelease.objects.create(resource=resource, year=year, released_at=when)
    elif row.released_at > now:
        row.released_at = when
        row.save(update_fields=["released_at"])


def _forget_to_come(resource, now: datetime) -> None:
    """A release still to come that won't now: dropped."""
    ResourceRelease.objects.filter(resource=resource, released_at__gt=now).delete()


def set_release_on(resource, day: date | None, now: datetime | None = None) -> None:
    """Its release date (None for none). Hidden, it's released then. Not saved."""
    now = now or timezone.now()
    resource.release_on = day
    _forget_to_come(resource, now)
    if day is not None and not resource.shown:
        _record(resource, release_moment(day), now)


def set_shown(resource, shown: bool, now: datetime | None = None) -> None:
    """Shown, it's released now; hidden, it goes until its release date, one
    still to come (one that's passed goes with it). Not saved."""
    now = now or timezone.now()
    if shown and not resource.shown:
        _forget_to_come(resource, now)
        _record(resource, now, now)
    if not shown and resource.release_on is not None:
        if resource.release_on <= sydney_today(now):
            resource.release_on = None
        else:
            _record(resource, release_moment(resource.release_on), now)
    resource.shown = shown
