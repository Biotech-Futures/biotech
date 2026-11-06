"""Dataset inventory, deterministic fingerprinting, and integrity checks."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta, timezone as datetime_timezone

from django.db.models import Count, Exists, F, OuterRef, Q

from dataset import (
    DATASET_NAME,
    DATASET_VERSION,
    SCENARIO_ANALYTICS_COVERAGE,
    DatasetConfig,
)


EMAIL_DOMAIN = "team4-synthetic.biotech.test"
EMAIL_SUFFIX = f"@{EMAIL_DOMAIN}"
ROW_PREFIX = "[TEAM4-SYNTH]"
MANIFEST_ENTITY = "team4_synthetic_dataset_manifest"
LOGIN_ENTITY = "user"


class DatasetVerificationError(RuntimeError):
    pass


def _synthetic_login_queryset():
    """Return login facts owned by this dataset without a synthetic entity type."""

    from apps.audit.models import AuditLog
    from apps.users.models import User

    users = User.objects.filter(email__endswith=EMAIL_SUFFIX)
    return AuditLog.objects.filter(
        action=AuditLog.ActionChoices.LOGIN,
        actor_user__in=users,
        after_state__dataset=DATASET_NAME,
    )


def _querysets():
    from email_samples import owned_metrics, EMAIL_METRIC_ENTITY
    from apps.services.models import EmailDeliveryRecipient
    from apps.announcements.models import Announcement, AnnouncementAudience, AnnouncementDelivery
    from apps.audit.models import AuditLog
    from apps.chat.models import Messages
    from apps.events.models import EventRsvp, Events
    from apps.groups.models import GroupMembership, Groups
    from apps.resources.models import (
        ResourceAccessEvent,
        ResourceAudience,
        Resources,
        RoleAssignmentHistory,
    )
    from apps.tasks.models import Task
    from apps.users.models import (
        AdminProfile,
        AdminScope,
        MentorAvailability,
        MentorProfile,
        StudentProfile,
        StudentSupervisor,
        SupervisorProfile,
        User,
        UserInterest,
    )

    users = User.objects.filter(email__endswith=EMAIL_SUFFIX)
    groups = Groups.objects.filter(group_name__startswith=ROW_PREFIX)
    resources = Resources.objects.filter(name__startswith=ROW_PREFIX)
    announcements = Announcement.objects.filter(title__startswith=ROW_PREFIX)
    events = Events.objects.filter(event_name__startswith=ROW_PREFIX)
    tasks = Task.objects.filter(name__startswith=ROW_PREFIX)
    messages = Messages.objects.filter(
        Q(group__in=groups) | Q(sender_user__in=users)
    ).distinct()

    return {
        "users": users,
        "student_profiles": StudentProfile.objects.filter(user__in=users),
        "mentor_profiles": MentorProfile.objects.filter(user__in=users),
        "supervisor_profiles": SupervisorProfile.objects.filter(user__in=users),
        "admin_profiles": AdminProfile.objects.filter(admin__in=users),
        "admin_scopes": AdminScope.objects.filter(user__in=users),
        "student_supervisors": StudentSupervisor.objects.filter(student_user__user__in=users),
        "mentor_availability": MentorAvailability.objects.filter(mentor_user__in=users),
        "user_interests": UserInterest.objects.filter(user__in=users),
        "role_assignments": RoleAssignmentHistory.objects.filter(user__in=users),
        "groups": groups,
        "memberships": GroupMembership.objects.filter(
            Q(group__in=groups) | Q(user__in=users)
        ).distinct(),
        "messages": messages,
        "login_events": _synthetic_login_queryset(),
        "manifests": AuditLog.objects.filter(entity_type=MANIFEST_ENTITY),
        "tasks": tasks,
        "resources": resources,
        "resource_access_events": ResourceAccessEvent.objects.filter(
            Q(resource__in=resources) | Q(user__in=users)
        ).distinct(),
        "resource_audiences": ResourceAudience.objects.filter(resource__in=resources),
        "announcements": announcements,
        "announcement_audiences": AnnouncementAudience.objects.filter(
            announcement__in=announcements
        ),
        "deliveries": AnnouncementDelivery.objects.filter(announcement__in=announcements),
        "email_metrics": owned_metrics(),
        "email_recipients": EmailDeliveryRecipient.objects.filter(metric__in=owned_metrics()),
        "email_markers": AuditLog.objects.filter(entity_type=EMAIL_METRIC_ENTITY),
        "events": events,
        "rsvps": EventRsvp.objects.filter(event__in=events),
    }


def snapshot_counts() -> dict[str, int]:
    return {name: queryset.count() for name, queryset in _querysets().items()}


def dataset_exists() -> bool:
    counts = snapshot_counts()
    return any(value for value in counts.values())


def unmanaged_business_counts() -> dict[str, int]:
    """Count business rows outside this tool's namespace.

    Framework/reference catalogues are intentionally omitted.  A non-empty
    result means aggregate API output will include more than the shared
    deterministic dataset.
    """

    from apps.announcements.models import Announcement
    from apps.audit.models import AuditLog
    from apps.chat.models import Messages
    from apps.events.models import Events
    from apps.groups.models import Groups
    from apps.resources.models import ResourceAccessEvent, Resources
    from apps.tasks.models import Task
    from apps.users.models import User

    from email_samples import EMAIL_METRIC_ENTITY, owned_metrics
    from apps.services.models import EmailDeliveryMetric
    counts = {
        "email_metrics": EmailDeliveryMetric.objects.exclude(pk__in=owned_metrics()).count(),
        "users": User.objects.exclude(email__endswith=EMAIL_SUFFIX).count(),
        "groups": Groups.objects.exclude(group_name__startswith=ROW_PREFIX).count(),
        "messages": Messages.objects.exclude(
            Q(group__group_name__startswith=ROW_PREFIX)
            | Q(sender_user__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "tasks": Task.objects.exclude(
            Q(name__startswith=ROW_PREFIX)
            | Q(group__group_name__startswith=ROW_PREFIX)
            | Q(assigned_user__email__endswith=EMAIL_SUFFIX)
            | Q(created_by__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "resources": Resources.objects.exclude(
            Q(name__startswith=ROW_PREFIX)
            | Q(uploaded_by__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "resource_access_events": ResourceAccessEvent.objects.exclude(
            Q(resource__name__startswith=ROW_PREFIX)
            | Q(user__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "announcements": Announcement.objects.exclude(
            Q(title__startswith=ROW_PREFIX)
            | Q(author_user__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "events": Events.objects.exclude(
            Q(event_name__startswith=ROW_PREFIX)
            | Q(host_user__email__endswith=EMAIL_SUFFIX)
        ).count(),
        "audit_logs": AuditLog.objects.exclude(
            Q(entity_type__in=[MANIFEST_ENTITY, EMAIL_METRIC_ENTITY])
            | Q(
                action=AuditLog.ActionChoices.LOGIN,
                actor_user__email__endswith=EMAIL_SUFFIX,
                after_state__dataset=DATASET_NAME,
            )
            | Q(actor_user__email__endswith=EMAIL_SUFFIX)
        ).count(),
    }
    return {name: count for name, count in counts.items() if count}


def _normalise(value):
    if hasattr(value, "tzinfo") and value.tzinfo is not None:
        return value.astimezone(datetime_timezone.utc).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def compute_fingerprint() -> str:
    """Hash stable business fields, deliberately excluding database primary keys."""

    from apps.announcements.models import Announcement, AnnouncementDelivery
    from apps.audit.models import AuditLog
    from apps.chat.models import Messages
    from apps.events.models import EventRsvp, Events
    from apps.groups.models import GroupMembership, Groups
    from apps.resources.models import (
        ResourceAccessEvent,
        ResourceAudience,
        Resources,
        RoleAssignmentHistory,
    )
    from apps.tasks.models import Task
    from apps.users.models import (
        MentorAvailability,
        MentorProfile,
        StudentProfile,
        StudentSupervisor,
        SupervisorProfile,
        User,
        UserInterest,
    )

    digest = hashlib.sha256()

    def feed(label: str, rows) -> None:
        digest.update(f"{label}\n".encode())
        for row in rows:
            payload = [_normalise(value) for value in row]
            digest.update(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode())
            digest.update(b"\n")

    users = User.objects.filter(email__endswith=EMAIL_SUFFIX).order_by("email")
    feed(
        "users",
        users.values_list(
            "email", "first_name", "last_name", "account_status", "is_active",
            "is_staff", "is_superuser", "timezone", "country__country_name",
            "state__state_name", "date_joined", "invited_at", "activated_at",
            # Login is normal demo use, not a change to the seeded facts.
        ).iterator(chunk_size=2000),
    )
    feed(
        "roles",
        RoleAssignmentHistory.objects.filter(user__in=users)
        .order_by("user__email", "role__role_name")
        .values_list("user__email", "role__role_name", "valid_from", "valid_to")
        .iterator(chunk_size=2000),
    )
    feed(
        "students",
        StudentProfile.objects.filter(user__in=users)
        .order_by("user__email")
        .values_list(
            "user__email", "pg_first_name", "pg_last_name", "pg_email",
            "school_name", "year_lvl", "parent_guardian_flag",
            "has_join_permission", "joinperm_responseID", "supervisor__user__email",
        )
        .iterator(chunk_size=2000),
    )
    feed(
        "mentors",
        MentorProfile.objects.filter(user__in=users)
        .order_by("user__email")
        .values_list("user__email", "background", "institution", "max_group_count")
        .iterator(chunk_size=2000),
    )
    feed(
        "supervisors",
        SupervisorProfile.objects.filter(user__in=users)
        .order_by("user__email")
        .values_list("user__email", "school_name")
        .iterator(chunk_size=2000),
    )
    feed(
        "student_supervisors",
        StudentSupervisor.objects.filter(student_user__user__in=users)
        .order_by("student_user__user__email", "supervisor_user__user__email")
        .values_list(
            "student_user__user__email",
            "supervisor_user__user__email",
            "relationship_type",
        )
        .iterator(chunk_size=2000),
    )
    feed(
        "mentor_availability",
        MentorAvailability.objects.filter(mentor_user__in=users)
        .order_by("mentor_user__email", "weekday", "start_time")
        .values_list("mentor_user__email", "weekday", "start_time", "end_time")
        .iterator(chunk_size=2000),
    )
    feed(
        "interests",
        UserInterest.objects.filter(user__in=users)
        .order_by("user__email", "interest__interest_desc")
        .values_list("user__email", "interest__interest_desc")
        .iterator(chunk_size=2000),
    )

    groups = Groups.objects.filter(group_name__startswith=ROW_PREFIX)
    feed(
        "groups",
        groups.order_by("group_name")
        .values_list("group_name", "year", "created_at", "deleted_at")
        .iterator(chunk_size=2000),
    )
    feed(
        "memberships",
        GroupMembership.objects.filter(group__in=groups)
        .order_by("group__group_name", "user__email")
        .values_list(
            "group__group_name", "user__email", "membership_role", "joined_at", "left_at"
        )
        .iterator(chunk_size=2000),
    )
    feed(
        "messages",
        Messages.objects.filter(group__in=groups)
        .order_by("message_text")
        .values_list(
            "group__group_name", "sender_user__email", "message_text", "message_type",
            "sent_at", "edited_at", "deleted_at",
        )
        .iterator(chunk_size=5000),
    )
    feed(
        "logins",
        _synthetic_login_queryset()
        .order_by("after_state__sequence")
        .values_list(
            "actor_user__email", "entity_type", "action", "created_at", "after_state"
        )
        .iterator(chunk_size=5000),
    )
    feed(
        "tasks",
        Task.objects.filter(name__startswith=ROW_PREFIX)
        .order_by("name")
        .values_list(
            "name", "task_type", "group__group_name", "assigned_user__email",
            "created_by__email", "creator_role", "status", "completed", "due_date",
            "created_at",
        )
        .iterator(chunk_size=2000),
    )
    resources = Resources.objects.filter(name__startswith=ROW_PREFIX)
    feed(
        "resource_audiences",
        ResourceAudience.objects.filter(resource__in=resources)
        .order_by("resource__name", "role__role_name")
        .values_list("resource__name", "role__role_name")
        .iterator(chunk_size=2000),
    )
    feed(
        "resource_labels",
        resources.order_by("name", "labels__name")
        .values_list("name", "labels__name")
        .iterator(chunk_size=2000),
    )
    feed(
        "resources",
        Resources.objects.filter(name__startswith=ROW_PREFIX)
        .order_by("name")
        .values_list(
            "name", "description", "kind", "visibility_scope", "group__group_name",
            "type__type_name", "uploaded_by__email", "uploaded_at", "deleted_at",
        )
        .iterator(chunk_size=2000),
    )
    feed(
        "resource_access_events",
        ResourceAccessEvent.objects.filter(
            Q(resource__in=resources) | Q(user__in=users)
        )
        .order_by("created_at", "resource__name", "user__email")
        .values_list("resource__name", "user__email", "created_at")
        .iterator(chunk_size=5000),
    )
    announcements = Announcement.objects.filter(title__startswith=ROW_PREFIX)
    feed(
        "announcements",
        announcements.order_by("title")
        .values_list("title", "visibility_scope", "published_at", "archived_at")
        .iterator(chunk_size=2000),
    )
    from apps.announcements.models import AnnouncementAudience

    feed(
        "announcement_audiences",
        AnnouncementAudience.objects.filter(announcement__in=announcements)
        .order_by("announcement__title", "role__role_name", "group__group_name")
        .values_list("announcement__title", "role__role_name", "group__group_name")
        .iterator(chunk_size=2000),
    )
    feed(
        "deliveries",
        AnnouncementDelivery.objects.filter(announcement__in=announcements)
        .order_by("started_at", "announcement__title")
        .values_list(
            "announcement__title", "started_at", "completed_at", "status",
            "recipient_count", "success_count", "failure_count",
            "initiated_by__email", "failed_recipients", "error_summary",
        )
        .iterator(chunk_size=2000),
    )
    events = Events.objects.filter(event_name__startswith=ROW_PREFIX)
    feed(
        "events",
        events.order_by("event_name")
        .values_list(
            "event_name", "event_type", "start_datetime", "ends_datetime",
            "event_timezone", "event_format", "location", "location_link",
        )
        .iterator(chunk_size=2000),
    )
    from apps.events.models import EventTargetGroup, EventTargetRole

    feed(
        "event_target_groups",
        EventTargetGroup.objects.filter(event__in=events)
        .order_by("event__event_name", "group__group_name")
        .values_list("event__event_name", "group__group_name")
        .iterator(chunk_size=2000),
    )
    feed(
        "event_target_roles",
        EventTargetRole.objects.filter(event__in=events)
        .order_by("event__event_name", "role__role_name")
        .values_list("event__event_name", "role__role_name")
        .iterator(chunk_size=2000),
    )
    feed(
        "rsvps",
        EventRsvp.objects.filter(event__in=events)
        .order_by("event__event_name", "user__email")
        .values_list("event__event_name", "user__email", "rsvp_status", "responded_at")
        .iterator(chunk_size=5000),
    )
    from email_samples import owned_metrics
    from apps.services.models import EmailDeliveryRecipient
    metrics = owned_metrics()
    feed('email_metrics', metrics.order_by('email_type', 'started_at').values_list(
        'email_type', 'source_mailbox', 'started_at', 'completed_at', 'status',
        'attempted_count', 'delivered_count', 'failed_count', 'initiated_by__email',
    ).iterator())
    feed('email_recipients', EmailDeliveryRecipient.objects.filter(metric__in=metrics)
         .order_by('metric__email_type', 'metric__started_at', 'email').values_list(
             'metric__email_type', 'metric__started_at', 'email', 'status', 'reason', 'user__email',
         ).iterator())
    return digest.hexdigest()


def load_manifest() -> dict:
    from apps.audit.models import AuditLog

    manifests = list(
        AuditLog.objects.filter(entity_type=MANIFEST_ENTITY).order_by("id")
    )
    if len(manifests) != 1:
        raise DatasetVerificationError(
            f"expected one dataset manifest, found {len(manifests)}"
        )
    payload = manifests[0].after_state
    if not isinstance(payload, dict):
        raise DatasetVerificationError("dataset manifest payload is invalid")
    if payload.get("dataset") != DATASET_NAME or payload.get("version") not in {6, DATASET_VERSION}:
        raise DatasetVerificationError("dataset manifest name or version is unsupported")
    return payload


def verify_dataset(*, check_migrations: bool = True) -> dict:
    try:
        from apps.admin.services.announcement import resolve_announcement_recipient_emails
    except ImportError:
        # Resolve the client baseline through its actual production helper.
        from apps.admin.services.announcement import (
            _resolve_recipient_emails as resolve_announcement_recipient_emails,
        )
    from apps.announcements.models import Announcement, AnnouncementDelivery
    from apps.chat.models import Messages
    from apps.groups.models import GroupMembership
    from apps.resources.models import RoleAssignmentHistory
    from apps.users.models import User

    if check_migrations:
        from safety import assert_migrations_current

        assert_migrations_current()

    manifest = load_manifest()
    config = DatasetConfig.from_manifest(manifest["config"])
    actual = snapshot_counts()
    expected = manifest.get("expected_counts")
    if not isinstance(expected, dict):
        raise DatasetVerificationError("dataset manifest expected_counts is invalid")
    if actual != expected:
        differences = {
            key: {"expected": expected.get(key), "actual": actual.get(key)}
            for key in sorted(set(expected or {}) | set(actual))
            if (expected or {}).get(key) != actual.get(key)
        }
        raise DatasetVerificationError(
            f"dataset row counts do not match the manifest: {differences}"
        )

    explicit = {
        "users": config.total_users,
        "student_profiles": config.students,
        "mentor_profiles": config.mentors,
        "supervisor_profiles": config.supervisors,
        "admin_profiles": config.admins,
        "admin_scopes": config.admins,
        "role_assignments": config.total_users,
        "groups": config.groups,
        "messages": config.messages,
        "login_events": config.login_events,
        "tasks": config.tasks,
        "resources": config.resources,
        "resource_access_events": config.resource_accesses,
        "announcements": config.announcements,
        "deliveries": config.announcement_delivery_count,
        "email_metrics": config.email_metric_count,
        "email_markers": config.email_metric_count,
        "events": config.events,
        "rsvps": config.rsvps,
        "manifests": 1,
    }
    mismatches = {
        key: {"configured": value, "actual": actual[key]}
        for key, value in explicit.items()
        if actual[key] != value
    }
    if mismatches:
        raise DatasetVerificationError(f"configured counts were not met: {mismatches}")

    users = User.objects.filter(email__endswith=EMAIL_SUFFIX)
    role_counts = RoleAssignmentHistory.objects.filter(
        user=OuterRef("pk"), valid_to__isnull=True
    )
    bad_roles = users.annotate(has_role=Exists(role_counts)).filter(has_role=False).count()
    if bad_roles:
        raise DatasetVerificationError(f"{bad_roles} generated users have no active role")

    bad_login_entities = _querysets()["login_events"].exclude(
        entity_type=LOGIN_ENTITY
    ).count()
    if bad_login_entities:
        raise DatasetVerificationError(
            f"{bad_login_entities} generated login events do not use entity_type=user"
        )

    groups = _querysets()["groups"]
    active_member = GroupMembership.objects.filter(
        group_id=OuterRef("group_id"),
        user_id=OuterRef("sender_user_id"),
        left_at__isnull=True,
    )
    bad_senders = (
        Messages.objects.filter(group__in=groups)
        .annotate(sender_is_member=Exists(active_member))
        .filter(sender_is_member=False)
        .count()
    )
    if bad_senders:
        raise DatasetVerificationError(
            f"{bad_senders} generated messages have a sender outside the active group"
        )

    deliveries = _querysets()["deliveries"].annotate(
        result_total=F("success_count") + F("failure_count")
    )
    bad_deliveries = deliveries.exclude(recipient_count=F("result_total")).count()
    if bad_deliveries:
        raise DatasetVerificationError(
            f"{bad_deliveries} delivery rows have inconsistent recipient totals"
        )

    from email_samples import owned_metrics
    for metric in owned_metrics().annotate(
        captured=Count('recipients'),
        delivered=Count('recipients', filter=Q(recipients__status='delivered')),
        failed=Count('recipients', filter=Q(recipients__status='failed')),
    ):
        if (metric.attempted_count, metric.delivered_count, metric.failed_count) != (metric.captured, metric.delivered, metric.failed):
            raise DatasetVerificationError(f'email counts differ from recipient facts: {metric.pk}')
        if metric.recipients.exclude(email__endswith=EMAIL_SUFFIX).exists():
            raise DatasetVerificationError('email sample contains a non-synthetic recipient')
        expected_status = 'success' if not metric.failed_count else 'failed' if not metric.delivered_count else 'partial'
        if metric.status != expected_status:
            raise DatasetVerificationError('email status differs from recipient outcomes')

    if config.email_mode == 'custom':
        from email_samples import custom_batch_plan
        metrics = owned_metrics().order_by('started_at', 'id')
        for metric, (kind, status, started_at, failures) in zip(metrics, custom_batch_plan(config)):
            if (metric.email_type, metric.status, metric.started_at, metric.attempted_count, metric.failed_count) != (kind, status, started_at, config.email_recipients, failures):
                raise DatasetVerificationError('custom email batch differs from the requested configuration')
            if metric.completed_at != started_at + timedelta(seconds=20):
                raise DatasetVerificationError('custom email completion time is inconsistent')
            if metric.recipients.filter(Q(user__isnull=True) | Q(user__is_active=False)).exists():
                raise DatasetVerificationError('custom email recipient is not an active synthetic user')
            if kind == 'announcement':
                delivery = deliveries.filter(started_at=started_at).select_related('announcement').get()
                expected_emails = set(resolve_announcement_recipient_emails(delivery.announcement_id, delivery.announcement.visibility_scope))
                if set(metric.recipients.values_list('email', flat=True)) != expected_emails:
                    raise DatasetVerificationError('custom announcement recipients differ from its audience')
                if (delivery.recipient_count, delivery.failure_count, delivery.status) != (config.email_recipients, failures, status):
                    raise DatasetVerificationError('custom announcement summary differs from its email batch')

    resource_querysets = _querysets()
    bad_resource_accesses = resource_querysets["resource_access_events"].exclude(
        resource__in=resource_querysets["resources"], user__in=users
    ).count()
    if bad_resource_accesses:
        raise DatasetVerificationError(
            f"{bad_resource_accesses} resource access events are outside the synthetic dataset"
        )

    if config.scenario == SCENARIO_ANALYTICS_COVERAGE:
        groups_with_counts = resource_querysets["groups"].annotate(
            member_count=Count("groupmembership", distinct=True),
            mentor_count=Count(
                "groupmembership",
                filter=Q(groupmembership__membership_role="mentor"),
                distinct=True,
            ),
            message_count=Count("messages", distinct=True),
        )
        expects_empty_group = bool(config.groups and (config.groups >= 2 or not config.messages))
        if expects_empty_group and not groups_with_counts.filter(member_count=0).exists():
            raise DatasetVerificationError(
                "analytics_coverage requires an empty generated group"
            )
        if (
            config.groups >= 2
            and bool(config.supervisors or config.students)
            and not groups_with_counts.filter(
                member_count__gt=0,
                mentor_count=0,
            ).exists()
        ):
            raise DatasetVerificationError(
                "analytics_coverage requires a populated group without a mentor"
            )
        if (
            config.groups >= 3
            and config.messages
            and bool(config.supervisors or config.mentors or config.students >= 2)
            and not groups_with_counts.filter(
                member_count__gt=0,
                message_count=0,
            ).exists()
        ):
            raise DatasetVerificationError(
                "analytics_coverage requires a populated group with zero messages"
            )

        resources_with_counts = resource_querysets["resources"].annotate(
            generated_access_count=Count(
                "access_events",
                filter=Q(access_events__user__in=users),
            )
        )
        if (
            config.resources >= 2
            and not resources_with_counts.filter(generated_access_count=0).exists()
        ):
            raise DatasetVerificationError(
                "analytics_coverage requires a zero-access generated resource"
            )
        if config.resources >= 3 and config.resource_accesses:
            hottest = resources_with_counts.order_by(
                "-generated_access_count"
            ).values_list("generated_access_count", flat=True).first()
            expected_hotspot = (config.resource_accesses + 1) // 2
            if hottest != expected_hotspot:
                raise DatasetVerificationError(
                    "analytics_coverage resource hotspot count differs from the expected "
                    f"{expected_hotspot}: {hottest}"
                )

        delivery_starts = set(
            resource_querysets["deliveries"].values_list("started_at", flat=True)
        )
        for index in range(13, min(config.deliveries if config.email_mode == 'coverage' else 0, 15) + 1):
            expected_start = config.as_of_datetime - timedelta(hours=10 + index)
            if expected_start not in delivery_starts:
                raise DatasetVerificationError(
                    "analytics_coverage delivery boundary row is missing at "
                    f"{expected_start.isoformat()}"
                )

        # Validate every delivery in the API's latest rolling window, including
        # small configurations that must degrade an impossible role/group
        # target to global without inventing recipients.
        coverage = set()
        window_start = config.as_of_datetime - timedelta(hours=24)
        window_deliveries = []
        if config.announcement_delivery_count:
            latest_delivery = resource_querysets["deliveries"].order_by(
                "-started_at"
            ).first()
            if latest_delivery is None:
                raise DatasetVerificationError(
                    "analytics_coverage requires generated delivery rows"
                )
            window_start = config.as_of_datetime - timedelta(hours=24)
            window_deliveries = list(
                resource_querysets["deliveries"]
                .filter(
                    started_at__gt=window_start,
                    started_at__lte=config.as_of_datetime,
                )
                .select_related("announcement")
                .prefetch_related("announcement__audiences__role")
            )
            for delivery in window_deliveries:
                audiences = list(delivery.announcement.audiences.all())
                resolved_recipients = set(
                    resolve_announcement_recipient_emails(
                        delivery.announcement_id,
                        delivery.announcement.visibility_scope,
                    )
                )
                if delivery.recipient_count != len(resolved_recipients):
                    raise DatasetVerificationError(
                        "analytics_coverage delivery recipient count does not "
                        "match the current resolvable audience: "
                        f"delivery={delivery.pk}, stored={delivery.recipient_count}, "
                        f"resolved={len(resolved_recipients)}"
                    )
                if (
                    delivery.success_count + delivery.failure_count
                    != delivery.recipient_count
                ):
                    raise DatasetVerificationError(
                        "analytics_coverage delivery outcomes do not sum to "
                        f"recipient count: delivery={delivery.pk}"
                    )
                expected_status = (
                    AnnouncementDelivery.Status.SUCCESS
                    if delivery.failure_count == 0
                    else AnnouncementDelivery.Status.FAILED
                    if delivery.success_count == 0
                    else AnnouncementDelivery.Status.PARTIAL
                )
                if delivery.status != expected_status:
                    raise DatasetVerificationError(
                        "analytics_coverage delivery status does not match its "
                        f"outcomes: delivery={delivery.pk}, stored={delivery.status}, "
                        f"expected={expected_status}"
                    )
                failed_emails = {
                    item.get("email")
                    for item in delivery.failed_recipients
                    if isinstance(item, dict)
                }
                if not failed_emails.issubset(resolved_recipients):
                    raise DatasetVerificationError(
                        "analytics_coverage delivery contains a failed recipient "
                        f"outside its current audience: delivery={delivery.pk}"
                    )
                if (
                    delivery.announcement.archived_at is not None
                    and delivery.started_at > delivery.announcement.archived_at
                ):
                    raise DatasetVerificationError(
                        "analytics_coverage reserved delivery occurs after its "
                        f"announcement was archived: delivery={delivery.pk}"
                    )
                role_names = {
                    audience.role.role_name.casefold()
                    for audience in audiences
                    if audience.role_id
                }
                has_group = any(audience.group_id for audience in audiences)
                if (
                    delivery.announcement.visibility_scope
                    == Announcement.VisibilityScope.GLOBAL
                    and not audiences
                ):
                    coverage.add("unattributed_global")
                if has_group and not role_names:
                    coverage.add("unattributed_group")
                if (
                    delivery.announcement.visibility_scope
                    not in {
                        Announcement.VisibilityScope.PUBLIC,
                        Announcement.VisibilityScope.GLOBAL,
                    }
                    and len(audiences) == 1
                    and not has_group
                    and len(role_names) == 1
                ):
                    coverage.add(next(iter(role_names)))

        # With eight announcements/deliveries, all three role populations, and
        # an active group membership, the deterministic pattern can represent
        # every Email role-attribution state. Smaller configurations preserve
        # requested counts and omit only impossible coverage categories.
        full_email_coverage_possible = (
            config.email_mode == 'coverage'
            and config.announcements >= 8
            and config.deliveries >= 8
            and bool(config.students)
            and bool(config.mentors)
            and bool(config.supervisors)
            and resource_querysets["memberships"].filter(user__is_active=True).exists()
        )
        if full_email_coverage_possible:
            required_coverage = {
                "unattributed_global",
                "unattributed_group",
                "student",
                "mentor",
                "supervisor",
            }
            missing_coverage = sorted(required_coverage - coverage)
            if missing_coverage:
                raise DatasetVerificationError(
                    "analytics_coverage email delivery window is missing: "
                    + ", ".join(missing_coverage)
                )

        if full_email_coverage_possible or (config.email_mode == 'custom' and config.admins):
            # Exercise the authenticated Django API boundary against the rows
            # generated above. This catches drift between the generator,
            # production analytics service, response serializer, and HTTP view
            # without requiring a separately running backend container.
            from apps.admin.analytics_views import EmailDeliveryAnalyticsView
            from rest_framework.test import APIRequestFactory, force_authenticate

            admin_profile = resource_querysets["admin_profiles"].select_related(
                "admin"
            ).first()
            if admin_profile is None:
                raise DatasetVerificationError(
                    "analytics_coverage API verification requires a generated admin"
                )
            request = APIRequestFactory().get(
                "/api/v1/admin/analytics/email/",
                HTTP_ACCEPT="application/json",
            )
            force_authenticate(request, user=admin_profile.admin)
            from unittest.mock import patch
            with patch('django.utils.timezone.now', return_value=config.as_of_datetime):
                response = EmailDeliveryAnalyticsView.as_view()(request)
            if response.status_code != 200:
                raise DatasetVerificationError(
                    "analytics_coverage Email API returned "
                    f"HTTP {response.status_code}"
                )
            payload = response.data.get("data") if isinstance(response.data, dict) else None
            if not isinstance(payload, dict):
                raise DatasetVerificationError(
                    "analytics_coverage Email API response is missing its data object"
                )

            totals = payload.get("totals")
            attribution = payload.get("role_attribution")
            role_rows = payload.get("status_by_role")
            if not isinstance(totals, dict) or not isinstance(attribution, dict):
                raise DatasetVerificationError(
                    "analytics_coverage Email API response is missing totals or attribution"
                )
            if not isinstance(role_rows, list):
                raise DatasetVerificationError(
                    "analytics_coverage Email API response is missing role rows"
                )
            returned_roles = {row.get("role") for row in role_rows if isinstance(row, dict)}
            if returned_roles != {"Student", "Mentor", "Supervisor"}:
                raise DatasetVerificationError(
                    "analytics_coverage Email API did not return all supported roles: "
                    f"{sorted(str(role) for role in returned_roles)}"
                )
            for metric in ("attempted", "delivered", "failed"):
                tracked = attribution.get(f"tracked_{metric}")
                unattributed = attribution.get(f"unattributed_{metric}")
                total = totals.get(metric)
                if not all(isinstance(value, int) for value in (tracked, unattributed, total)):
                    raise DatasetVerificationError(
                        "analytics_coverage Email API returned invalid "
                        f"{metric} counters"
                    )
                field = {'attempted': 'recipient_count', 'delivered': 'success_count', 'failed': 'failure_count'}[metric]
                expected_announcement_total = sum(getattr(row, field) for row in window_deliveries)
                if tracked + unattributed != expected_announcement_total:
                    raise DatasetVerificationError(
                        "analytics_coverage Email API attribution does not reconcile "
                        f"{metric} totals"
                    )
                metric_field = {'attempted': 'attempted_count', 'delivered': 'delivered_count', 'failed': 'failed_count'}[metric]
                expected_metric_total = sum(owned_metrics().filter(
                    started_at__gt=window_start, started_at__lte=config.as_of_datetime,
                ).values_list(metric_field, flat=True))
                if total != expected_metric_total:
                    raise DatasetVerificationError(f'Email API {metric} does not match generated metrics')
            if any(row.get("opened") is not None for row in role_rows):
                raise DatasetVerificationError(
                    "analytics_coverage Email API must keep unavailable opened counts null"
                )

    fingerprint = compute_fingerprint()
    if fingerprint != manifest.get("fingerprint"):
        raise DatasetVerificationError(
            "dataset fingerprint differs from the manifest; rows were modified"
        )

    return {
        "dataset": DATASET_NAME,
        "version": manifest['version'],
        "config": config.to_manifest(),
        "counts": actual,
        "fingerprint": fingerprint,
    }
