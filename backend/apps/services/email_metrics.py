"""Privacy-minimal, fail-open metrics for actual email send outcomes."""

import logging
from email.utils import parseaddr

from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import EmailDeliveryMetric


logger = logging.getLogger(__name__)


def mailbox_address(value: str | None) -> str:
    """Return the bare mailbox from either an address or a display-name header."""
    _name, address = parseaddr(value or "")
    return address.strip().lower()


def record_email_delivery(
    email_type: str,
    *,
    source_mailbox: str | None,
    attempted: int,
    delivered: int,
    failed: int,
    initiated_by=None,
    started_at=None,
    completed_at=None,
) -> None:
    """Persist one aggregate send result without ever affecting email delivery."""
    attempted = max(int(attempted), 0)
    delivered = max(int(delivered), 0)
    failed = max(int(failed), 0)
    mailbox = mailbox_address(source_mailbox)
    if not mailbox or attempted == 0:
        return

    if delivered and failed:
        status = EmailDeliveryMetric.Status.PARTIAL
    elif delivered:
        status = EmailDeliveryMetric.Status.SUCCESS
    else:
        status = EmailDeliveryMetric.Status.FAILED

    try:
        # A savepoint keeps a metrics failure from poisoning a caller's outer
        # transaction after the email itself has already been sent.
        with transaction.atomic():
            EmailDeliveryMetric.objects.create(
                email_type=email_type,
                source_mailbox=mailbox,
                attempted_count=attempted,
                delivered_count=delivered,
                failed_count=failed,
                status=status,
                initiated_by=(
                    initiated_by
                    if getattr(initiated_by, "pk", None)
                    else None
                ),
                started_at=started_at or timezone.now(),
                completed_at=completed_at or timezone.now(),
            )
    except (DatabaseError, ValueError, TypeError):
        logger.exception(
            "email_metric.write_failed type=%s mailbox=%s", email_type, mailbox
        )
