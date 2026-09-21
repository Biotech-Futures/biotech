from django.db import models
from django.conf import settings


class MatchRun(models.Model):
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='admin_match_runs',
    )
    run_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField()

    class Meta:
        db_table = 'admin_match_run'


class AdminView(models.Model):
    class VisibilityChoices(models.TextChoices):
        SYSTEM = 'system', 'System Default'
        SHARED = 'shared', 'Admin Shared'
        PRIVATE = 'private', 'Private'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_custom_views'
    )
    visibility = models.CharField(
        max_length=32,
        choices=VisibilityChoices.choices,
        default=VisibilityChoices.SHARED
    )
    is_default = models.BooleanField(default=False)

    # Filtering criteria
    target_roles = models.JSONField(default=list)
    account_status = models.CharField(max_length=32, default='all')
    engagement_status = models.CharField(max_length=32, default='all')
    advanced_conditions = models.JSONField(default=list)

    # Table layout
    visible_columns = models.JSONField(default=list)

    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_user_views'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name
