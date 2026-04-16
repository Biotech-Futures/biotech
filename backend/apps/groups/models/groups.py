from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Groups(models.Model):
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT) # Protect to prevent deletion when referenced track is gone 
    creation_datetime = models.DateTimeField(default=timezone.now) # Default to current time on creation
    deleted_flag = models.BooleanField(default=False) # Default to False for better data integrity
    deleted_datetime = models.DateTimeField(null=True, blank=True) # Allow null/blank for groups that aren't deleted

    class Meta:
        db_table = 'groups'
        indexes = [
        models.Index(fields=['track']),
        models.Index(fields=['deleted_flag']),
        models.Index(fields=['creation_datetime']),
        ]

        constraints = [
            # Ensure deleted_flag is True if deleted_datetime is set
            models.CheckConstraint(
                condition=(
                    (Q(deleted_flag=True)  & Q(deleted_datetime__isnull=False)) |
                    (Q(deleted_flag=False) & Q(deleted_datetime__isnull=True))
                ),
                name='group_deleted_flag_datetime_consistent',
            ),
            # Ensure group names are unique within the same track
            models.UniqueConstraint(
                fields=['track', 'group_name'],
                name='unique_group_name_per_track'
            ),
            # Ensure deleted_datetime is after creation_datetime if set
            models.CheckConstraint(
                condition=Q(deleted_datetime__gte=F('creation_datetime')) | Q(deleted_datetime__isnull=True),
                name='deleted_after_creation'
            ),
            models.CheckConstraint(
                check=~Q(group_name__regex=r'^\s*$'),
                name='group_name_not_empty'
            ),
            # Ensure creation_datetime is not in the future
            models.CheckConstraint(
                condition=Q(creation_datetime__lte=models.functions.Now()),
                name='group_creation_not_future'
            ),  
        ]
    
    def __str__(self):
        return self.group_name
