from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class GroupMembership(models.Model):
    group = models.ForeignKey("Groups", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    membership_role = models.CharField(max_length=50, blank=True, default="")
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "group_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                condition=Q(left_at__isnull=True),
                name="unique_active_group_membership",
            ),
            models.CheckConstraint(
                condition=Q(left_at__gte=F("joined_at")) | Q(left_at__isnull=True),
                name="group_membership_left_after_joined",
            ),
        ]
        indexes = [
            models.Index(fields=["group"]),
            models.Index(fields=["user"]),
            models.Index(fields=["left_at"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"
