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

# Years a date filter may name. Far enough either side of any log row, and
# clear of the ends of Python's calendar, where adding a day or moving to
# UTC overflows.
MIN_YEAR, MAX_YEAR = 1900, 9998
# The largest user id the database can hold (a 64-bit key).
MAX_USER_ID = 2**63 - 1
# The largest level the level column can hold.
MAX_LEVEL = 32767


def _is_date_only(value: str) -> bool:
    return bool(_DATE_ONLY.fullmatch(value))


def _parse_moment(value: str, *, end_of_day: bool) -> datetime:
    """An ISO datetime, or a date (its start, or the start of the next day
    for ``end_of_day``), in UTC. Without an offset it's taken as UTC. Raises
    ValueError for anything malformed or outside MIN_YEAR..MAX_YEAR."""
    try:
        # Dates first: parse_datetime would read "2026-10-01" as midnight.
        if _is_date_only(value):
            day = parse_date(value)
            if day is None or not MIN_YEAR <= day.year <= MAX_YEAR:
                raise ValueError(value)
            if end_of_day:
                day += timedelta(days=1)
            moment = datetime.combine(day, time.min)
        else:
            moment = parse_datetime(value)
            if moment is None or not MIN_YEAR <= moment.year <= MAX_YEAR:
                raise ValueError(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=dt_timezone.utc)
        # Converted here, so an offset that moves it out of range is this
        # filter's error, not the database's.
        return moment.astimezone(dt_timezone.utc)
    except OverflowError as exc:
        raise ValueError(value) from exc


def _parse_level(value: str) -> int:
    if value.isdecimal():
        level = int(value)
    else:
        level = logging.getLevelName(value.upper())
        if not isinstance(level, int):
            raise ValueError(value)
    if not 0 <= level <= MAX_LEVEL:
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
            errors[param] = (
                f"Use an ISO date or datetime between {MIN_YEAR} and {MAX_YEAR}, "
                "e.g. 2026-10-01 or 2026-10-01T09:30:00+10:00."
            )
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
            errors["level"] = f"Use DEBUG, INFO, WARNING, ERROR or CRITICAL, or a number up to {MAX_LEVEL}."

    source = (params.get("source") or "").strip()
    if source:
        qs = qs.filter(logger_name__startswith=source)

    user = (params.get("user") or "").strip()
    if user:
        # isdecimal, not isdigit: "³" is a digit int() can't read. Anything
        # that isn't a plain number is searched for in the email.
        if not user.isdecimal():
            qs = qs.filter(user__email__icontains=user)
        elif int(user) > MAX_USER_ID:
            errors["user"] = "No user has an id that large."
        else:
            qs = qs.filter(user_id=int(user))

    text = (params.get("q") or "").strip()
    if text:
        qs = qs.filter(message__icontains=text)

    request_id = (params.get("request_id") or "").strip()
    if request_id:
        qs = qs.filter(request_id=request_id)

    if errors:
        raise ValidationError(errors)
    return qs.order_by("-created_at", "-id")
