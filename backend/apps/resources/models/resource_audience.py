from django.db import models
from django.db.models import Q


class ResourceAudience(models.Model):
    resource = models.ForeignKey("Resources", on_delete=models.CASCADE, related_name="audiences")
    role = models.ForeignKey("Roles", on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = "resource_audience"
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["role"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__isnull=False),
                name="resource_audience_requires_role",
            ),
            models.UniqueConstraint(
                fields=["resource", "role"],
                condition=Q(role__isnull=False),
                name="unique_resource_role_audience",
            ),
        ]
        verbose_name = "Resource Audience"
        verbose_name_plural = "Resource Audiences"

    def __str__(self):
        return f"{self.resource} -> {self.role}"

