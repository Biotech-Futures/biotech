from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class RoleAssignmentHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey("Roles", on_delete=models.PROTECT)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(blank=True, null=True)

    class Meta:
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
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.user} as {self.role} from {self.valid_from} to {self.valid_to or 'present'}"
