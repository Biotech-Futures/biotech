"""Deterministic configuration for the Team 4 local analytics dataset."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone


DATASET_NAME = "team4-analytics-standard"
DATASET_VERSION = 7
SYSTEM_EMAIL_TYPES = (
    'login_code', 'password_reset', 'registration_student', 'registration_mentor',
    'guardian_consent_request', 'unread_messages', 'submission_reminder', 'rsvp_reminder',
)
EMAIL_TYPES = ('announcement', *SYSTEM_EMAIL_TYPES)
EMAIL_STATUSES = ('success', 'partial', 'failed')
EMAIL_CONFIG_FIELDS = (
    'email_mode', 'email_batches', 'email_type', 'email_status',
    'email_recipients', 'email_start', 'email_end',
)


def current_snapshot_time() -> str:
    """Capture today's clock once; the saved manifest remains reproducible."""
    return datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
SCENARIO_ANALYTICS_COVERAGE = "analytics_coverage"
SCENARIO_UNIFORM = "uniform"
DATASET_SCENARIOS = (
    SCENARIO_ANALYTICS_COVERAGE,
    SCENARIO_UNIFORM,
)


def parse_as_of(value: str) -> datetime:
    """Parse an aware ISO-8601 instant and normalise it to UTC."""

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(
            "--as-of must be an ISO-8601 datetime, for example "
            "2026-09-01T00:00:00Z"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--as-of must include a UTC offset or Z")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class DatasetConfig:
    """All user-adjustable inputs for one deterministic generator run."""

    admins: int = 2
    supervisors: int = 12
    mentors: int = 24
    students: int = 120
    groups: int = 24
    messages: int = 720
    login_events: int = 600
    tasks: int = 180
    resources: int = 30
    resource_accesses: int = 1200
    announcements: int = 12
    deliveries: int = 24
    events: int = 12
    rsvps: int = 120
    scenario: str = SCENARIO_ANALYTICS_COVERAGE
    seed: int = 3888
    as_of: str = field(default_factory=current_snapshot_time)
    email_mode: str = 'coverage'
    email_batches: int = 48
    email_type: str = 'mixed'
    email_status: str = 'mixed'
    email_recipients: int = 4
    email_start: str = ''
    email_end: str = ''

    @property
    def total_users(self) -> int:
        return self.admins + self.supervisors + self.mentors + self.students

    @property
    def participant_users(self) -> int:
        return self.supervisors + self.mentors + self.students

    @property
    def as_of_datetime(self) -> datetime:
        return parse_as_of(self.as_of)

    @property
    def active_users(self) -> int:
        # Matches the eight-account status cycle in generator._status_for.
        return self.admins + sum(
            (count // 8) * 4 + sum(count % 8 >= position for position in (1, 2, 3, 5))
            for count in (self.students, self.mentors, self.supervisors)
        )

    @property
    def email_start_datetime(self) -> datetime:
        return parse_as_of(self.email_start) if self.email_start else self.as_of_datetime - timedelta(hours=23)

    @property
    def email_end_datetime(self) -> datetime:
        return parse_as_of(self.email_end) if self.email_end else self.as_of_datetime - timedelta(minutes=5)

    @property
    def email_metric_count(self) -> int:
        return self.email_batches if self.email_mode == 'custom' else self.deliveries * 2

    @property
    def announcement_delivery_count(self) -> int:
        if self.email_mode != 'custom':
            return self.deliveries
        if self.email_type == 'announcement':
            return self.email_batches
        if self.email_type == 'mixed':
            return (self.email_batches + len(EMAIL_TYPES) - 1) // len(EMAIL_TYPES)
        return 0

    def validate(self) -> "DatasetConfig":
        count_names = (
            "admins",
            "supervisors",
            "mentors",
            "students",
            "groups",
            "messages",
            "login_events",
            "tasks",
            "resources",
            "resource_accesses",
            "announcements",
            "deliveries",
            "events",
            "rsvps",
        )
        for name in count_names:
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"--{name.replace('_', '-')} cannot be negative")
            if value > 2_000_000:
                raise ValueError(
                    f"--{name.replace('_', '-')} exceeds the 2,000,000-row safety limit"
                )

        if self.scenario not in DATASET_SCENARIOS:
            choices = ", ".join(DATASET_SCENARIOS)
            raise ValueError(f"--scenario must be one of: {choices}")

        parse_as_of(self.as_of)

        if self.email_mode not in ('coverage', 'custom'):
            raise ValueError('email_mode must be coverage or custom')
        if self.email_type not in ('mixed', *EMAIL_TYPES):
            raise ValueError('email_type is not a supported email type')
        if self.email_status not in ('mixed', *EMAIL_STATUSES):
            raise ValueError('email_status must be mixed, success, partial, or failed')
        for name in ('email_batches', 'email_recipients'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2_000_000:
                raise ValueError(f'{name} must be a whole number from 0 to 2,000,000')
        for name in ('email_start', 'email_end'):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > 80:
                raise ValueError(f'{name} must be a timezone-aware ISO-8601 value')
            if value:
                parse_as_of(value)
        if self.email_mode == 'custom' and self.email_batches:
            if not self.admins:
                raise ValueError('email batches require at least one admin')
            if not 1 <= self.email_recipients <= self.active_users:
                raise ValueError(f'email_recipients must be from 1 to {self.active_users} active synthetic users')
            if self.email_status == 'partial' and self.email_recipients < 2:
                raise ValueError('partial email status requires at least 2 recipients')
            if self.email_batches * self.email_recipients > 2_000_000:
                raise ValueError('email batches × recipients exceeds the 2,000,000-row safety limit')
            if self.email_start_datetime > self.email_end_datetime:
                raise ValueError('email start must be at or before email end')
            if (self.email_end_datetime - self.email_start_datetime).total_seconds() < self.email_batches - 1:
                raise ValueError('email time range must allow at least one second between batches')
            if self.email_end_datetime + timedelta(seconds=20) > self.as_of_datetime:
                raise ValueError('email end must be at least 20 seconds before the dataset clock')

        if self.messages and (not self.groups or not self.participant_users):
            raise ValueError(
                "messages require at least one group and one student, mentor, or supervisor"
            )
        if self.login_events and not self.total_users:
            raise ValueError("login events require at least one user")
        if (self.resources or self.announcements or self.announcement_delivery_count) and not self.admins:
            raise ValueError(
                "resources, announcements, and deliveries require at least one admin"
            )
        if self.resource_accesses and (not self.resources or not self.total_users):
            raise ValueError(
                "resource accesses require at least one resource and one user"
            )
        if self.announcement_delivery_count and not self.announcements:
            raise ValueError("deliveries require at least one announcement")
        if self.tasks and not (self.groups or self.total_users):
            raise ValueError("tasks require at least one group or user")
        if self.rsvps and (not self.events or not self.total_users):
            raise ValueError("RSVPs require at least one event and one user")
        if self.rsvps > self.events * self.total_users:
            raise ValueError(
                "RSVP count exceeds the number of unique event/user pairs"
            )
        return self

    def to_manifest(self) -> dict[str, int | str]:
        payload = asdict(self)
        payload["as_of"] = self.as_of_datetime.isoformat()
        if self.email_mode == 'custom':
            payload['email_start'] = self.email_start_datetime.isoformat()
            payload['email_end'] = self.email_end_datetime.isoformat()
        return payload

    @classmethod
    def from_manifest(cls, payload: dict) -> "DatasetConfig":
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in payload.items() if key in allowed}
        return cls(**values).validate()
