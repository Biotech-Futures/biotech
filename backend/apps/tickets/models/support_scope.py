from django.conf import settings
from django.db import models


class SupportScope(models.Model):
    """Marker table: a row means the user can work the support queue.

    Deliberately mirrors ``users.AdminScope`` field-for-field (DEC-014④,
    DEC-019 A5) so a reviewer comparing the two tables sees no difference to
    explain. Admins are support-capable without a row here — that OR lives in
    :func:`apps.tickets.permissions.is_support`, which is its only home.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_scope",
    )

    class Meta:
        db_table = 'support_scope'
        verbose_name = "Support Scope"
        verbose_name_plural = "Support Scopes"
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_support_scope_per_user'),
        ]
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user} -> support"
