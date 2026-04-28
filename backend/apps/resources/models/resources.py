from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Resources(models.Model):
    class VisibilityScope(models.TextChoices):
        PUBLIC = "public", "Public"
        ROLE = "role", "Role"
        TRACK = "track", "Track"
        GROUP = "group", "Group"
        SCOPED = "scoped", "Scoped"

    class ResourceKind(models.TextChoices):
        FILE = "file", "File"
        PAGE = "page", "Page"

    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    type = models.ForeignKey('ResourceType', on_delete=models.PROTECT, related_name='resources', null=True, blank=True)

    kind = models.CharField(
        max_length=50,
        choices=ResourceKind.choices,
        default=ResourceKind.FILE,
    )
    file_mime_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    storage_key = models.CharField(max_length=255, null=True, blank=True)

    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    group = models.ForeignKey("groups.Groups", on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    visibility_scope = models.CharField(
        max_length=50,
        choices=VisibilityScope.choices,
        default=VisibilityScope.ROLE,
    )
    uploaded_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'resources'
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        indexes = [
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['track']),
            models.Index(fields=['visibility_scope']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            # Ensure deleted_at is after uploaded_at if set
            models.CheckConstraint(
                condition=Q(deleted_at__gte=F('uploaded_at')) | Q(deleted_at__isnull=True),
                name='deleted_after_upload'
            ),
            # Ensure description is not empty
            models.CheckConstraint(
                condition=~Q(description=''),
                name='resource_description_not_empty'
            ),
        ]

    def __str__(self):
        return self.name or f"Resource {self.id}"
