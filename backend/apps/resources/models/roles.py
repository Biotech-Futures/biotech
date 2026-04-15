from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Roles(models.Model):
    role_name = models.CharField(unique=True, max_length=255)

    class Meta:
        db_table = 'roles'
        verbose_name = "Role"
        verbose_name_plural = "Roles"

        constraints = [
            # Ensure role names are unique and not empty
            models.CheckConstraint(
                condition=~Q(role_name=''),
                name='role_name_not_empty'
            )
        ]

    def __str__(self):
        return self.role_name
