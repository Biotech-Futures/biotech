from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Announcement(models.Model):
    class VisibilityScope(models.TextChoices):
        PUBLIC = "public", "Public"
        ROLE = "role", "Role"
        TRACK = "track", "Track"
        SCOPED = "scoped", "Scoped"

    author_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    visibility_scope = models.CharField(
        max_length=50,
        choices=VisibilityScope.choices,
        default=VisibilityScope.PUBLIC,
    )
    published_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "announcements"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["author_user"]),
            models.Index(fields=["track"]),
            models.Index(fields=["visibility_scope"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["archived_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(archived_at__gte=F("published_at")) | Q(archived_at__isnull=True),
                name="announcement_archived_after_published",
            ),
        ]

    def __str__(self):
        return self.title


class AnnouncementAudience(models.Model):
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="audiences",
    )
    role = models.ForeignKey("resources.Roles", on_delete=models.CASCADE, null=True, blank=True)
    track = models.ForeignKey("groups.Tracks", on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = "announcement_audience"
        indexes = [
            models.Index(fields=["announcement"]),
            models.Index(fields=["role"]),
            models.Index(fields=["track"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__isnull=False) | Q(track__isnull=False),
                name="announcement_audience_requires_role_or_track",
            ),
            models.UniqueConstraint(
                fields=["announcement", "role"],
                condition=Q(track__isnull=True) & Q(role__isnull=False),
                name="unique_announcement_role_audience",
            ),
            models.UniqueConstraint(
                fields=["announcement", "track"],
                condition=Q(role__isnull=True) & Q(track__isnull=False),
                name="unique_announcement_track_audience",
            ),
            models.UniqueConstraint(
                fields=["announcement", "role", "track"],
                condition=Q(role__isnull=False) & Q(track__isnull=False),
                name="unique_announcement_role_track_audience",
            ),
        ]

    def __str__(self):
        target = self.role or self.track
        return f"{self.announcement} -> {target}"


class AnnouncementDelivery(models.Model):
    """
    One row per "notify" attempt for an announcement.

    Replaces the previous ``fail_silently=True`` send_mail call which had no
    audit trail — operators need to be able to answer "did the announcement
    actually go out, and to whom did it bounce?" without grepping mail server
    logs.
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"   # every recipient accepted
        PARTIAL = "partial", "Partial"   # at least one succeeded, at least one failed
        FAILED = "failed", "Failed"      # zero succeeded
        # Note: the API also returns ``"skipped"`` when the audience resolves to
        # zero recipients or the announcement id is unknown. ``"skipped"`` is a
        # *wire-only* status — it is never persisted on a delivery row, so it is
        # deliberately absent from this enum. If you ever need to persist a
        # skipped attempt, add ``SKIPPED`` here AND a migration.

    # Max number of failing addresses to persist on a single delivery row.
    # Anything beyond this is summarised into ``error_summary`` so a 50k-user
    # announcement doesn't blow up the row.
    FAILED_RECIPIENTS_CAP = 50

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcement_deliveries",
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    recipient_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    failed_recipients = models.JSONField(default=list, blank=True)
    error_summary = models.TextField(blank=True, default="")

    class Meta:
        db_table = "announcement_delivery"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["announcement"]),
            models.Index(fields=["initiated_by"]),
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
        ]

    def __str__(self):
        return (
            f"Delivery #{self.pk} ({self.status}, "
            f"{self.success_count}/{self.recipient_count})"
        )
