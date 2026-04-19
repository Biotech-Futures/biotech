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
