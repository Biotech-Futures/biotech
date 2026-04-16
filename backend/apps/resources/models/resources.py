from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Resources(models.Model):
    resource_name = models.CharField(max_length=255)
    resource_description = models.CharField(max_length=255)
    resource_type = models.ForeignKey('ResourceType', on_delete=models.PROTECT, related_name='resources', null=True, blank=True)
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
            # Ensure upload_datetime is not in the future
            models.CheckConstraint(
                condition=Q(upload_datetime__lte=models.functions.Now()),
                name='resource_upload_not_future'
            ),
        ]

    def __str__(self):
        return self.resource_name or f"Resource {self.id}"
