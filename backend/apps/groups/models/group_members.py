from django.conf import settings
from django.db import models


class GroupMembership(models.Model):
    group = models.ForeignKey('Groups', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'user'],
                name='unique_group_membership'
            ),
        ]
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"
