from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Groups(models.Model):
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey("Tracks", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(blank=True, null=True)
    year_min = models.PositiveSmallIntegerField(blank=True, null=True)
    year_max = models.PositiveSmallIntegerField(blank=True, null=True)
    lead_mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_groups",
    )
    max_members = models.PositiveIntegerField(default=8)

    class Meta:
        db_table = "groups"
        indexes = [
            models.Index(fields=["track"]),
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["track", "group_name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_group_name_per_track",
            ),
            models.CheckConstraint(
                condition=Q(deleted_at__isnull=True) | Q(deleted_at__gte=F("created_at")),
                name="group_deleted_after_created",
            ),
            models.CheckConstraint(
                condition=~Q(group_name__regex=r"^\s*$"),
                name="group_name_not_empty",
            ),
        ]

    def __str__(self):
        return self.group_name

    @property
    def is_deleted(self):
        return self.deleted_at is not None
