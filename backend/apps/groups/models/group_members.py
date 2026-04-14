from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class GroupMembers(models.Model):
    group = models.ForeignKey('Groups', models.CASCADE) # thinking cascade since if a group is deleted, members should be removed from that group
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE) # Cascade to remove user from group if user is deleted
    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'user'],
                name='unique_group_user'
            )
            # TODO: implement some sort of constraint or check which only allows a user to be added to an active (not deleted) group
        ] # Composite unique constraint to ensure each user is unique per group, as composite keys aren't natively supported
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user} in {self.group}"
