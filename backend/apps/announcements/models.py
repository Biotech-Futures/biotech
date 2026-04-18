from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone


class Announcement(models.Model):
    message = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    group = models.ForeignKey('groups.Groups', on_delete=models.CASCADE, null=True, blank=True)
    target_role = models.ForeignKey('resources.Roles', on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(default=None, blank=True, null=True)

    class Meta:
        db_table = 'announcements'
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['target_role']),
            models.Index(fields=['created_by']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gt=F('start_date')),
                name='announcement_end_after_start'
            ),
            models.CheckConstraint(
                condition=Q(deleted_flag=False) | (Q(deleted_flag=True) & Q(deleted_datetime__isnull=False)),
                name='announcement_deleted_flag_and_datetime'
            ),
            # Mentor announcements must have a group; admin can have either or neither
            models.CheckConstraint(
                condition=Q(group__isnull=True) | Q(target_role__isnull=True),
                name='announcement_not_both_group_and_role'
            ),
        ]

    def __str__(self):
        if self.target_role:
            return f"Announcement by {self.created_by} targeting role {self.target_role}"
        if self.group:
            return f"Announcement by {self.created_by} for group {self.group}"
        return f"Announcement by {self.created_by} for everyone"
