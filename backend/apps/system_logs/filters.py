"""The System Logs filters, shared by the list and the export so the two
always show the same rows."""
import logging
import re
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.db.models import QuerySet
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError

from .models import SystemLogEntry

_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_date_only(value: str) -> bool:
    return bool(_DATE_ONLY.fullmatch(value))


def _parse_moment(value: str, *, end_of_day: bool) -> datetime:
    """An ISO datetime, or a date (its start, or the start of the next day
    for ``end_of_day``). Without an offset it's taken as UTC."""
    # Dates first: parse_datetime would read "2026-10-01" as midnight.
    if _is_date_only(value):
        day = parse_date(value)
        if day is None:
            raise ValueError(value)
        if end_of_day:
            day += timedelta(days=1)
        moment = datetime.combine(day, time.min)
    else:
        moment = parse_datetime(value)
        if moment is None:
            raise ValueError(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_timezone.utc)
    return moment


def _parse_level(value: str) -> int:
    if value.isdigit():
        return int(value)
    level = logging.getLevelName(value.upper())
    if not isinstance(level, int):
        raise ValueError(value)
    return level


def filter_entries(params) -> QuerySet:
    """Log rows matching the query ``params``, newest first:

    * ``from`` / ``to`` – ISO datetimes or dates (``to`` a date includes that day)
    * ``level`` – that level and above, by name (``WARNING``) or number
    * ``source`` – loggers whose name starts with this (``apps.services``)
    * ``user`` – a user id, or part of the user's email
    * ``q`` – text in the message
    * ``request_id`` – exactly this request id
    """
    qs = SystemLogEntry.objects.all()
    errors = {}

    for param, lookup, end_of_day in (("from", "created_at__gte", False), ("to", "created_at__lt", True)):
        value = (params.get(param) or "").strip()
        if not value:
            continue
        try:
            moment = _parse_moment(value, end_of_day=end_of_day)
        except ValueError:
            errors[param] = "Use an ISO date or datetime, e.g. 2026-10-01 or 2026-10-01T09:30:00+10:00."
            continue
        if param == "to" and not _is_date_only(value):
            # An exact datetime "to" is inclusive.
            lookup = "created_at__lte"
        qs = qs.filter(**{lookup: moment})

    level = (params.get("level") or "").strip()
    if level:
        try:
            qs = qs.filter(level__gte=_parse_level(level))
        except ValueError:
            errors["level"] = "Use DEBUG, INFO, WARNING, ERROR or CRITICAL."

    source = (params.get("source") or "").strip()
    if source:
        qs = qs.filter(logger_name__startswith=source)

    user = (params.get("user") or "").strip()
    if user:
        qs = qs.filter(user_id=int(user)) if user.isdigit() else qs.filter(user__email__icontains=user)

    text = (params.get("q") or "").strip()
    if text:
        qs = qs.filter(message__icontains=text)

    request_id = (params.get("request_id") or "").strip()
    if request_id:
        qs = qs.filter(request_id=request_id)

    if errors:
        raise ValidationError(errors)
    return qs.order_by("-created_at", "-id")
