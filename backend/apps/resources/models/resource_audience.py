from django.db import models
from django.db.models import Q


class ResourceAudience(models.Model):
    resource = models.ForeignKey("Resources", on_delete=models.CASCADE, related_name="audiences")
    role = models.ForeignKey("Roles", on_delete=models.CASCADE, null=True, blank=True)
    track = models.ForeignKey("groups.Tracks", on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = "resource_audience"
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["role"]),
            models.Index(fields=["track"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__isnull=False) | Q(track__isnull=False),
                name="resource_audience_requires_role_or_track",
            ),
            models.UniqueConstraint(
                fields=["resource", "role"],
                condition=Q(track__isnull=True) & Q(role__isnull=False),
                name="unique_resource_role_audience",
            ),
            models.UniqueConstraint(
                fields=["resource", "track"],
                condition=Q(role__isnull=True) & Q(track__isnull=False),
                name="unique_resource_track_audience",
            ),
            models.UniqueConstraint(
                fields=["resource", "role", "track"],
                condition=Q(role__isnull=False) & Q(track__isnull=False),
                name="unique_resource_role_track_audience",
            ),
        ]
        verbose_name = "Resource Audience"
        verbose_name_plural = "Resource Audiences"

    def __str__(self):
        target = self.role or self.track
        return f"{self.resource} -> {target}"

