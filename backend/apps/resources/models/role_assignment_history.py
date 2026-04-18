from django.conf import settings
from django.db import models
<<<<<<< Updated upstream
from django.db.models import F, Q
from django.utils import timezone
=======
from django.db.models import Q, F

>>>>>>> Stashed changes


class RoleAssignmentHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
<<<<<<< Updated upstream
    role = models.ForeignKey("Roles", on_delete=models.PROTECT)
=======
    role = models.ForeignKey('Roles', on_delete=models.PROTECT)
>>>>>>> Stashed changes
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(blank=True, null=True)

    class Meta:
<<<<<<< Updated upstream
        db_table = "user_role_assignment"
        verbose_name = "User Role Assignment"
        verbose_name_plural = "User Role Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "valid_from"],
                name="unique_user_role_start",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__gte=F("valid_from")),
                name="valid_to_after_valid_from",
=======
        db_table = 'user_role_assignment'
        verbose_name = "User Role Assignment"
        verbose_name_plural = "User Role Assignments"
        constraints = [
            models.UniqueConstraint(fields=['user', 'role', 'valid_from'], name='unique_user_role_start'),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=F('valid_from')),
                name='valid_to_after_valid_from'
>>>>>>> Stashed changes
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.user} as {self.role} from {self.valid_from} to {self.valid_to or 'present'}"
