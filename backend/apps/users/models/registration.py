import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class RegistrationWindow(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    # Who last saved the dates (Management > Registration), and when.
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    # A year Start new year began (Management > New Year): closed until its
    # opening date is set. Years before it stay open while no date is set.
    closed_until_set = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(opens_at__isnull=True) | Q(closes_at__isnull=True)
                | Q(closes_at__gt=F("opens_at")),
                name="registration_window_order",
            ),
        ]

    def is_open(self, now):
        if self.opens_at is None and self.closed_until_set:
            return False
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
    # Who registered (the first student, or the mentor): once a year, as
    # someone back for a later year registers again (apps.users.returning).
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student_count = models.PositiveSmallIntegerField(default=1)
    group = models.ForeignKey("groups.Groups", null=True, blank=True, on_delete=models.PROTECT)
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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["window", "student"], name="registration_once_per_window"),
        ]


class RegistrationStudent(models.Model):
    submission = models.ForeignKey(
        RegistrationSubmission, related_name="participants", on_delete=models.CASCADE,
    )
    # One registration's students; a student back for a later year is in
    # that year's too.
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField()
    guardian_phone = models.CharField(max_length=50, blank=True)
    guardian_relationship = models.CharField(max_length=255, blank=True)
    grouping_preference = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "position"], name="registration_student_position_unique",
            ),
        ]
