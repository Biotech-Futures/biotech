from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Announcement(models.Model):
    """
    Announcements/News posts for the BIOTech Futures platform.
    Supports audience targeting and both external/internal links.
    """

    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('student', 'Students Only'),
        ('mentor', 'Mentors Only'),
        ('supervisor', 'Supervisors Only'),
        ('admin', 'Administrators Only'),
    ]

    # Core fields
    title = models.CharField(max_length=255, help_text="Announcement title")
    summary = models.TextField(help_text="Brief description shown in list view")
    content = models.TextField(
        blank=True,
        null=True,
        help_text="Full announcement content (for detail page)"
    )

    # Metadata
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements',
        help_text="User who created this announcement"
    )
    created_datetime = models.DateTimeField(auto_now_add=True)
    updated_datetime = models.DateTimeField(auto_now=True)

    # Targeting
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='all',
        help_text="Target audience for this announcement"
    )

    # Links (optional - can have external link OR internal route, not both)
    external_link = models.URLField(
        blank=True,
        null=True,
        help_text="External URL (e.g., https://example.com)"
    )
    internal_route = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Frontend route path (e.g., /events/123)"
    )

    # Management
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(blank=True, null=True)

    # Priority/Featured
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pin to top of announcements list"
    )

    class Meta:
        db_table = 'announcements'
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-is_pinned', '-created_datetime']  # Pinned first, then newest
        indexes = [
            models.Index(fields=['audience']),
            models.Index(fields=['created_datetime']),
            models.Index(fields=['is_pinned']),
            models.Index(fields=['deleted_flag']),
        ]
        constraints = [
            # Ensure deleted items have a deleted datetime
            models.CheckConstraint(
                condition=(
                    models.Q(deleted_flag=False) |
                    (models.Q(deleted_flag=True) & models.Q(deleted_datetime__isnull=False))
                ),
                name='announcement_deleted_flag_datetime_check'
            ),
        ]

    def clean(self):
        """
        Validate that external_link and internal_route are not both set.
        """
        if self.external_link and self.internal_route:
            raise ValidationError({
                'external_link': 'Cannot set both external_link and internal_route. Choose one.',
                'internal_route': 'Cannot set both external_link and internal_route. Choose one.'
            })

    def save(self, *args, **kwargs):
        # Run validation before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_audience_display()})"
