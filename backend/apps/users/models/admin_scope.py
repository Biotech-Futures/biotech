from django.conf import settings
from django.db import models


class AdminScope(models.Model):
    """Marker table: a row means the user is an admin (single global tier)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'admin_scope'
        verbose_name = "Admin Scope"
        verbose_name_plural = "Admin Scopes"
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_admin_scope_per_user'),
        ]
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user} -> admin"
