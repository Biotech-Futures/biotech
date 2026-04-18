from django.db import models
from django.db.models import F, Q
from django.utils import timezone

class Groups(models.Model):
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT)
    creation_datetime = models.DateTimeField(default=timezone.now)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(default=None, blank=True, null=True)

    class Meta:
        db_table = 'groups'
        indexes = [
            models.Index(fields=['track']),
            models.Index(fields=['deleted_flag']),
            models.Index(fields=['creation_datetime']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['track', 'group_name'],
                condition=Q(deleted_flag=False),
                name='unique_active_group_name_per_track'
            ),
            models.CheckConstraint(
                condition=Q(deleted_flag=False) | (Q(deleted_flag=True) & Q(deleted_datetime__isnull=False)),
                name='group_deleted_after_created'
            ),
            models.CheckConstraint(
                condition=~Q(group_name__regex=r'^\s*$'),
                name='group_name_not_empty'
            ),
        ]

    def __str__(self):
        return self.group_name

    @property
    def is_deleted(self):
        return self.deleted_flag
