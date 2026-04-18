from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class RoleAssignmentHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        related_name="user_role_assignments",
    )
    role = models.ForeignKey(
        "Roles",
        on_delete=models.PROTECT,
        null=True,
        related_name="role_assignments",
    )
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "user_role_assignment"
        verbose_name = "Role Assignment History"
        verbose_name_plural = "Role Assignment Histories"
        constraints = [
            models.UniqueConstraint(fields=['user', 'role', 'valid_from'], name='unique_user_role_start'),
            # Ensure valid_to is after valid_from if valid_to is set
            models.CheckConstraint(
                condition=Q(valid_to__gte=F('valid_from')),
                name='valid_to_after_valid_from'
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['role']),
        ]
    def __str__(self):
        return f"{self.user} as {self.role} from {self.valid_from} to {self.valid_to or 'present'}"
