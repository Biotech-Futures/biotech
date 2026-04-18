from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Groups(models.Model):
    group_name = models.CharField(max_length=255)
<<<<<<< Updated upstream
    track = models.ForeignKey("Tracks", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(blank=True, null=True)
    year_min = models.PositiveSmallIntegerField(blank=True, null=True)
    year_max = models.PositiveSmallIntegerField(blank=True, null=True)
=======
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(default=None, blank=True, null=True)
    year_min = models.SmallIntegerField(null=True, blank=True)
    year_max = models.SmallIntegerField(null=True, blank=True)
>>>>>>> Stashed changes
    lead_mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
<<<<<<< Updated upstream
        related_name="led_groups",
    )
    max_members = models.PositiveSmallIntegerField(default=8, blank=True, null=True)
=======
        related_name='led_groups',
    )
    max_members = models.IntegerField(default=8, null=True, blank=True)
>>>>>>> Stashed changes

    class Meta:
        db_table = "groups"
        indexes = [
<<<<<<< Updated upstream
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
=======
            models.Index(fields=['track']),
            models.Index(fields=['created_at']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
>>>>>>> Stashed changes
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
