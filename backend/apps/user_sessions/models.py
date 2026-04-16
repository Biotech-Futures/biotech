import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


def default_session_expiry():
    age = getattr(settings, "SESSION_COOKIE_AGE", 86400)
    return timezone.now() + timedelta(seconds=age)


def default_sid():
    return uuid.uuid4().hex


class UserSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sid = models.CharField(max_length=64, unique=True, default=default_sid)
    created_at = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_session_expiry)
    ended_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_session"
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["sid"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["last_activity_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(last_activity_at__gte=F("created_at")),
                name="user_session_activity_after_created",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gte=F("created_at")),
                name="user_session_expires_after_created",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__gte=F("created_at")) | Q(ended_at__isnull=True),
                name="user_session_ended_after_created",
            ),
            models.CheckConstraint(
                condition=Q(revoked_at__gte=F("created_at")) | Q(revoked_at__isnull=True),
                name="user_session_revoked_after_created",
            ),
        ]

    def __str__(self):
        return f"{self.user} [{self.sid}]"

    @property
    def is_open(self):
        now = timezone.now()
        return self.ended_at is None and self.revoked_at is None and self.expires_at > now


class Alert(models.Model):
    session = models.ForeignKey("UserSession", on_delete=models.CASCADE, related_name="alerts")
    created_at = models.DateTimeField(default=timezone.now)
    error_reason = models.CharField(max_length=255)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alert"
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session"]),
            models.Index(fields=["resolved"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(error_reason=""),
                name="alert_reason_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(resolved=False, resolved_at__isnull=True)
                | Q(resolved=True, resolved_at__isnull=False),
                name="alert_resolved_matches_timestamp",
            ),
            models.CheckConstraint(
                condition=Q(resolved_at__gte=F("created_at")) | Q(resolved_at__isnull=True),
                name="alert_resolved_after_created",
            ),
        ]

    def __str__(self):
        return f"{self.session_id} @ {self.created_at}: {self.error_reason}"


Sessions = UserSession
Alerts = Alert
