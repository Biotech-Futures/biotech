from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Resources(models.Model):
    class VisibilityScope(models.TextChoices):
        PUBLIC = "public", "Public"
        ROLE = "role", "Role"
        TRACK = "track", "Track"
        SCOPED = "scoped", "Scoped"

    resource_name = models.CharField(max_length=255)
    resource_description = models.CharField(max_length=255)
    resource_type = models.ForeignKey('ResourceType', on_delete=models.PROTECT, related_name='resources', null=True, blank=True)
    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    visibility_scope = models.CharField(
        max_length=50,
        choices=VisibilityScope.choices,
        default=VisibilityScope.ROLE,
    )
    upload_datetime = models.DateTimeField(default=timezone.now)
    uploader_user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'resources'
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        indexes = [
            models.Index(fields=['uploader_user_id']),
            models.Index(fields=['track']),
            models.Index(fields=['visibility_scope']),
        ]
        constraints = [
            # Ensure deleted_flag is always either True or False
            models.CheckConstraint(
                condition=Q(deleted_datetime__isnull=True) | Q(deleted_flag=True),
                name='deleted_flag_true_if_deleted_datetime'
            ),
            # Ensure resource names are unique if provided
            models.CheckConstraint(
                condition=Q(deleted_datetime__gte=F('upload_datetime')) | Q(deleted_datetime__isnull=True),
                name='deleted_after_upload'
            ),
            # Ensure resource_description is not empty
            models.CheckConstraint(
                condition=~Q(resource_description=''),
                name='resource_description_not_empty'
            ),
        ]

    def __str__(self):
        return self.resource_name or f"Resource {self.id}"

    @property
    def uploaded_at(self):
        return self.upload_datetime

    @property
    def deleted_at(self):
        return self.deleted_datetime
