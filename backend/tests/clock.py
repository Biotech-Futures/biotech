"""Run the test suite as if the calendar had moved on, so a test that only
passes before some date fails today instead of the day it would start
blocking deploys.

    TEST_CLOCK_SHIFT_DAYS=400 python manage.py test tests \\
        --settings=config.settings_test --testrunner=tests.clock.ShiftedClockRunner

CI runs this beside the normal run (see .github/workflows/main_biotechbe.yml).
A year and more ahead always crosses a New Year and every fixed date in the
coming year, so anything tied to today's date or year shows up with over a
year to spare.

The shift is made where ``django.utils.timezone.now()`` reads the clock, so
everything that stamps or compares times through it moves together: model
defaults, the app's checks, and the tests' own ``timezone.now()``. Real
datetimes still count as datetimes, so the rest of Django is unaffected.
"""
from __future__ import annotations

import datetime as _dt
import os
from unittest import mock

from django.test.runner import DiscoverRunner


def shifted_datetime(shift: _dt.timedelta) -> type:
    """A stand-in for ``datetime.datetime`` whose ``now()`` is ``shift`` ahead."""

    class _Meta(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, _dt.datetime)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, _dt.datetime)

    class ShiftedDatetime(_dt.datetime, metaclass=_Meta):
        @classmethod
        def now(cls, tz=None):
            return _dt.datetime.now(tz) + shift

        @classmethod
        def utcnow(cls):
            return _dt.datetime.utcnow() + shift

    return ShiftedDatetime


def _target(now: _dt.datetime) -> _dt.datetime:
    """Where the run's clock starts: ``TEST_CLOCK_AT`` (an ISO time in UTC, or
    ``new-year`` for half an hour into the next New Year in UTC, where a date
    "a day ago" is still last year), else ``TEST_CLOCK_SHIFT_DAYS`` days from
    now."""
    at = os.environ.get("TEST_CLOCK_AT", "")
    if at == "new-year":
        return _dt.datetime(now.year + 1, 1, 1, tzinfo=_dt.timezone.utc) + _dt.timedelta(minutes=30)
    if at:
        return _dt.datetime.fromisoformat(at).replace(tzinfo=_dt.timezone.utc)
    return now + _dt.timedelta(days=int(os.environ.get("TEST_CLOCK_SHIFT_DAYS", "0")))


class ShiftedClockRunner(DiscoverRunner):
    """The usual runner, with the clock moved (see ``_target``)."""

    def run_tests(self, *args, **kwargs):
        now = _dt.datetime.now(_dt.timezone.utc)
        target = _target(now)
        shift = target - now
        print(f"Clock moved to {target:%Y-%m-%d %H:%M} UTC for this run.")
        with mock.patch("django.utils.timezone.datetime", shifted_datetime(shift)):
            return super().run_tests(*args, **kwargs)
