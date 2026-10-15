import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class RegistrationWindow(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(opens_at__isnull=True) | Q(closes_at__isnull=True)
                | Q(closes_at__gt=F("opens_at")),
                name="registration_window_order",
            ),
        ]

    def is_open(self, now):
        return (self.opens_at is None or self.opens_at <= now) and (
            self.closes_at is None or now < self.closes_at
        )


class RegistrationInvitation(models.Model):
    nonce = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    window = models.ForeignKey(RegistrationWindow, on_delete=models.PROTECT)
    journey = models.CharField(max_length=32, default="student_individual", editable=False)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def status_at(self, now):
        if self.revoked_at:
            return "revoked"
        if self.used_at:
            return "used"
        return "expired" if self.expires_at <= now else "active"


class RegistrationSubmission(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.UUIDField(unique=True)
    request_digest = models.CharField(max_length=64)
    window = models.ForeignKey(RegistrationWindow, on_delete=models.PROTECT)
    journey = models.CharField(max_length=32, default="student_individual")
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    invitation = models.OneToOneField(
        RegistrationInvitation, null=True, blank=True, on_delete=models.PROTECT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_registrations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    supervisor_details = models.JSONField(default=dict)
    supervisor_mode = models.CharField(max_length=16, default="school")
    guardian_phone = models.CharField(max_length=50, blank=True)
    guardian_relationship = models.CharField(max_length=255, blank=True)
    grouping_preference = models.CharField(max_length=32, blank=True)
    source = models.JSONField(default=dict)
