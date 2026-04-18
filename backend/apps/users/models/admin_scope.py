from django.conf import settings
from django.db import models
from django.db.models import Q


class AdminScope(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey(
        "groups.Tracks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_global = models.BooleanField(default=False)

    class Meta:
        db_table = "admin_scope"
        verbose_name = "Admin Scope"
        verbose_name_plural = "Admin Scopes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "track"],
                condition=Q(is_global=False),
                name="unique_admin_scope_per_track",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_global=True),
                name="unique_global_admin_scope",
            ),
            models.CheckConstraint(
                condition=(Q(is_global=True) & Q(track__isnull=True))
                | (Q(is_global=False) & Q(track__isnull=False)),
                name="admin_scope_global_or_track",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["track"]),
        ]

    def __str__(self):
        return f"{self.user} -> {'global' if self.is_global else self.track}"
