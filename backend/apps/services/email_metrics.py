"""Privacy-minimal, fail-open metrics for actual email send outcomes."""

import logging
from collections.abc import Iterable, Mapping
from email.utils import parseaddr

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from .models import EmailDeliveryMetric, EmailDeliveryRecipient


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
    recipients: Iterable[str] | None = None,
    missed: Mapping[str, str] | None = None,
) -> None:
    """Persist one aggregate send result without ever affecting email delivery.

    ``recipients`` are the addresses the send was made to and ``missed`` maps
    each one it didn't reach to the reason; given either, one recipient row
    is kept per address (see ``EmailDeliveryRecipient``).
    """
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
            metric = EmailDeliveryMetric.objects.create(
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
        return

    if recipients is None and not missed:
        return
    try:
        # Its own savepoint too: the counts stay even if the list can't be kept.
        with transaction.atomic():
            EmailDeliveryRecipient.objects.bulk_create(
                _recipient_rows(metric, recipients or (), missed or {})
            )
    except (DatabaseError, ValueError, TypeError):
        # Not the addresses themselves: they are personal data.
        logger.exception("email_metric.recipients_write_failed type=%s", email_type)


def _recipient_rows(metric, recipients: Iterable[str], missed: Mapping[str, str]):
    """One row per distinct address, failed when ``missed`` names it."""
    reasons = {}
    for value, reason in missed.items():
        address = mailbox_address(value)
        if address:
            reasons[address] = reason or ""
    addresses: list[str] = []
    seen: set[str] = set()
    for value in (*recipients, *reasons):
        address = mailbox_address(value)
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    user_ids = dict(
        get_user_model().objects.annotate(lower_email=Lower("email"))
        .filter(lower_email__in=addresses)
        .values_list("lower_email", "id")
    )
    return [
        EmailDeliveryRecipient(
            metric=metric,
            user_id=user_ids.get(address),
            email=address,
            status=(
                EmailDeliveryRecipient.Status.FAILED
                if address in reasons
                else EmailDeliveryRecipient.Status.DELIVERED
            ),
            reason=str(reasons.get(address, ""))[:120],
        )
        for address in addresses
    ]
