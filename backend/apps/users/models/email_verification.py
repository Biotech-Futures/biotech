from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class EmailVerification(models.Model):
    """QuickEmailVerification's latest answer for one address, kept so the
    same address isn't paid for twice (apps.users.email_verification).

    Only answers from the service are stored: a call that failed (timeout,
    outage, bad response) leaves nothing here, so the address is tried again
    next time. A valid or invalid answer is reused until it is older than the
    configured maximum age (QEV_RESULT_MAX_AGE_DAYS); an unknown one only for
    QEV_UNKNOWN_MAX_AGE_HOURS, then it's checked again."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"
        # QEV's "unknown", and "valid" on a domain that accepts every address.
        UNKNOWN = "unknown", "Unknown"

    REUSABLE_STATUSES = (Status.VALID, Status.INVALID)

    # Stored stripped and lower case, so one address is one row.
    email = models.EmailField(max_length=254, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    # QEV's reason, e.g. "rejected_email" or "accepted_email".
    reason = models.CharField(max_length=32, blank=True, default="")
    accept_all = models.BooleanField(default=False)
    disposable = models.BooleanField(default=False)
    role = models.BooleanField(default=False)
    free = models.BooleanField(default=False)
    # None when the service didn't say.
    safe_to_send = models.BooleanField(null=True, blank=True)
    # The service's suggested correction for a likely typo, if any.
    did_you_mean = models.CharField(max_length=254, blank=True, default="")
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "email_verification"
        verbose_name = "Email Verification"
        verbose_name_plural = "Email Verifications"
        ordering = ["-checked_at"]

    @staticmethod
    def normalise(email) -> str:
        return str(email or "").strip().lower()

    @classmethod
    def reusable(cls, emails, *, max_age_days: int, unknown_max_age_hours=None) -> dict:
        """The stored answers for ``emails`` still fresh enough to reuse, keyed
        by normalised address: valid or invalid within ``max_age_days`` days,
        unknown within ``unknown_max_age_hours`` (QEV_UNKNOWN_MAX_AGE_HOURS)."""
        addresses = {cls.normalise(email) for email in emails} - {""}
        if not addresses:
            return {}
        if unknown_max_age_hours is None:
            unknown_max_age_hours = int(getattr(settings, "QEV_UNKNOWN_MAX_AGE_HOURS", 24))
        now = timezone.now()
        rows = cls.objects.filter(email__in=addresses).filter(
            Q(status__in=cls.REUSABLE_STATUSES, checked_at__gte=now - timedelta(days=max_age_days))
            | Q(status=cls.Status.UNKNOWN, checked_at__gte=now - timedelta(hours=unknown_max_age_hours))
        )
        return {row.email: row for row in rows}

    def save(self, *args, **kwargs):
        self.email = self.normalise(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email}: {self.status}"


class EmailVerificationCredits(models.Model):
    """How many QuickEmailVerification credits each key has left, as the
    service last reported it, which low-credit alerts have gone out since the
    last top-up, which keys are out of credit, and how many lookups have been
    made today. Always a single row (pk=1).

    ``remaining``, ``updated_at`` and ``alerted_thresholds`` are the paid key's
    (QEV_PAID_API_KEY), the one alerts follow; the free key's balance is kept
    for display only."""

    SINGLETON_PK = 1

    # None until the first answer from the service is read.
    remaining = models.PositiveIntegerField(null=True, blank=True)
    # When ``remaining`` was last read from the service.
    updated_at = models.DateTimeField(null=True, blank=True)
    # The thresholds whose alert has been sent, e.g. [500]. A threshold is
    # dropped again once the balance is back at or above it (a top-up).
    alerted_thresholds = models.JSONField(default=list, blank=True)
    # The free key's (QEV_API_KEY) balance and when it was read: for display
    # only, never alerted on. None until it's first reported.
    free_remaining = models.PositiveIntegerField(null=True, blank=True)
    free_updated_at = models.DateTimeField(null=True, blank=True)
    # Paid lookups made on ``lookups_on`` (a UTC date), for the daily cap.
    # The count starts again on a new day.
    lookups_on = models.DateField(null=True, blank=True)
    lookups_today = models.PositiveIntegerField(default=0)
    # When each key (the free QEV_API_KEY, the paid QEV_PAID_API_KEY) was last
    # found out of credit; None while it has credit. Checks skip it until it's
    # due a retry (apps.users.email_verification).
    free_exhausted_at = models.DateTimeField(null=True, blank=True)
    paid_exhausted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_verification_credits"
        verbose_name = "Email Verification Credits"
        verbose_name_plural = "Email Verification Credits"

    def save(self, *args, **kwargs):
        # Pin the row to one primary key so a second row can never exist.
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """Return the credits row, creating it with defaults if missing."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj

    def __str__(self):
        return "Unknown" if self.remaining is None else f"{self.remaining} credits remaining"


class EmailVerificationRequest(models.Model):
    """One real request sent to QuickEmailVerification, for usage reporting
    (Team 4's analytics). A free key falling back to the paid one is two rows.
    Failed requests are kept too; sandbox requests and stored answers reused
    are not. No email address is kept. Kept indefinitely, from the deploy
    that added it."""

    KEY_CHOICES = [("free", "Free"), ("paid", "Paid")]

    requested_at = models.DateTimeField(default=timezone.now, db_index=True)
    # The key used, by name only ("free" or "paid"), never the key itself.
    key = models.CharField(max_length=8, choices=KEY_CHOICES)
    # valid, invalid or unknown when QEV answered; otherwise why there was no
    # answer (out_of_credit, request_timeout, connection_error, http_<code>, ...).
    outcome = models.CharField(max_length=32)
    # 1 for an answer, 0 for a failure (assumed: QEV hasn't confirmed failures are free).
    credits = models.PositiveSmallIntegerField(default=0)
    # The key's balance QEV reported with this answer; None when it didn't say.
    remaining = models.PositiveIntegerField(null=True, blank=True)
    # The feature that asked (CALLERS in apps.users.email_verification); blank if unknown.
    caller = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        db_table = "email_verification_request"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.requested_at:%Y-%m-%d %H:%M} {self.key} {self.outcome}"
