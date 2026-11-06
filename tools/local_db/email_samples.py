"""Synthetic local email facts for the client analytics contract; never sends mail."""
from datetime import timedelta
import random

from dataset import EMAIL_TYPES, EMAIL_STATUSES, SYSTEM_EMAIL_TYPES

EMAIL_METRIC_ENTITY = 'team4_synthetic_email_metric'
SYSTEM_TYPES = SYSTEM_EMAIL_TYPES
MAILBOXES = ('info@biotechfutures.org', 'connect@biotechfutures.org')


def owned_metrics():
    from apps.audit.models import AuditLog
    from apps.services.models import EmailDeliveryMetric
    return EmailDeliveryMetric.objects.filter(pk__in=AuditLog.objects.filter(
        entity_type=EMAIL_METRIC_ENTITY,
    ).values('entity_id'))


def custom_batch_plan(config):
    """Yield exact, reproducible settings for each custom batch, in time order."""
    types = EMAIL_TYPES if config.email_type == 'mixed' else (config.email_type,)
    statuses = EMAIL_STATUSES if config.email_recipients >= 2 else ('success', 'failed')
    duration = config.email_end_datetime - config.email_start_datetime
    for index in range(config.email_batches):
        kind = types[index % len(types)]
        status = statuses[(index + index // len(EMAIL_TYPES)) % len(statuses)] if config.email_status == 'mixed' else config.email_status
        failures = 0 if status == 'success' else config.email_recipients if status == 'failed' else max(1, config.email_recipients // 2)
        started_at = config.email_start_datetime + duration * index / max(1, config.email_batches - 1)
        yield kind, status, started_at, failures


def create_email_samples(config, buckets, announcements=None):
    from apps.admin.services.announcement import _resolve_recipient_emails
    from apps.announcements.models import AnnouncementDelivery
    from apps.audit.models import AuditLog
    from apps.services.models import EmailDeliveryMetric, EmailDeliveryRecipient
    from verification import ROW_PREFIX

    if not config.email_metric_count:
        return
    actor = buckets['admin'][0]
    people = sorted(sum((buckets[role] for role in ('student', 'mentor', 'supervisor', 'admin')), []), key=lambda u: u.email)
    by_email = {user.email: user for user in people}

    def record(kind, index, started_at, addresses, failures):
        addresses = sorted(set(addresses))
        delivered = len(addresses) - failures
        metric = EmailDeliveryMetric.objects.create(
            email_type=kind, source_mailbox=MAILBOXES[(index - 1) % len(MAILBOXES)],
            attempted_count=len(addresses), delivered_count=delivered, failed_count=failures,
            status='success' if not failures else 'failed' if not delivered else 'partial',
            initiated_by=actor, started_at=started_at,
            completed_at=started_at + timedelta(seconds=20),
        )
        EmailDeliveryRecipient.objects.bulk_create([
            EmailDeliveryRecipient(
                metric=metric, user=by_email.get(email), email=email,
                status='failed' if i < failures else 'delivered',
                reason='Synthetic demo failure' if i < failures else '',
            ) for i, email in enumerate(addresses)
        ])
        AuditLog.objects.create(
            actor_user=actor, entity_type=EMAIL_METRIC_ENTITY, entity_id=metric.pk,
            action=AuditLog.ActionChoices.IMPORT, created_at=config.as_of_datetime,
            after_state={'synthetic': True, 'email_type': kind},
        )

    if config.email_mode == 'custom':
        from apps.announcements.models import Announcement, AnnouncementAudience
        active_people = [person for person in people if person.is_active]
        rng = random.Random(config.seed)
        # All custom announcement sends share an explicit per-person audience,
        # so every requested count also agrees with the production resolver.
        selected = sorted(rng.sample(active_people, config.email_recipients), key=lambda person: person.email)
        announcement_rows = announcements or []
        if config.announcement_delivery_count:
            for announcement in announcement_rows[:config.announcement_delivery_count]:
                announcement.audiences.all().delete()
                AnnouncementAudience.objects.bulk_create([
                    AnnouncementAudience(announcement=announcement, user=person) for person in selected
                ])
                announcement.visibility_scope = Announcement.VisibilityScope.ROLE_BASED
                announcement.published_at = min(announcement.published_at, config.email_start_datetime - timedelta(hours=1))
                announcement.archived_at = None
                announcement.save(update_fields=['visibility_scope', 'published_at', 'archived_at'])
        announcement_index = 0
        for index, (kind, status, started_at, failures) in enumerate(custom_batch_plan(config), 1):
            recipients = selected if kind == 'announcement' else sorted(rng.sample(active_people, config.email_recipients), key=lambda person: person.email)
            addresses = [person.email for person in recipients]
            if kind == 'announcement':
                announcement = announcement_rows[announcement_index % len(announcement_rows)]
                announcement_index += 1
                AnnouncementDelivery.objects.create(
                    announcement=announcement, initiated_by=actor, started_at=started_at,
                    completed_at=started_at + timedelta(seconds=20), status=status,
                    recipient_count=len(addresses), success_count=len(addresses) - failures,
                    failure_count=failures,
                    failed_recipients=[{'email': email, 'error': 'Synthetic demo failure'} for email in addresses[:min(failures, 50)]],
                    error_summary='Synthetic demo failure' if failures else '',
                )
            record(kind, index, started_at, addresses, failures)
        return

    deliveries = AnnouncementDelivery.objects.filter(
        announcement__title__startswith=ROW_PREFIX,
    ).select_related('announcement').order_by('started_at', 'id')
    for index, delivery in enumerate(deliveries, 1):
        announcement = delivery.announcement
        addresses = _resolve_recipient_emails(announcement.pk, announcement.visibility_scope)
        record('announcement', index, delivery.started_at, addresses, delivery.failure_count)

    # One system-email batch per configured announcement batch, with several
    # types and both mailboxes. Every address belongs to a synthetic user.
    for index in range(config.deliveries):
        recipients = [people[(index + offset) % len(people)].email for offset in range(min(4, len(people)))]
        failures = (0, 1, len(recipients))[index % 3]
        offset = timedelta(hours=index + 1, minutes=15) if index < 12 else timedelta(days=1 + index % 13, minutes=15)
        record(SYSTEM_TYPES[index % len(SYSTEM_TYPES)], index + 1,
               config.as_of_datetime - offset, recipients, failures)
