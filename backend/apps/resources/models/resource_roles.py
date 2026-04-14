from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class ResourceRoles(models.Model):
    resource = models.ForeignKey('Resources', on_delete=models.CASCADE, related_name='resourceroles')
    role = models.ForeignKey('Roles', on_delete=models.CASCADE)

    class Meta:
        db_table = 'resource_roles'
        indexes = [
            models.Index(fields=['role'])
        ]
        constraints = [
            models.UniqueConstraint(fields=['resource', 'role'], name='pk_resource_role')
        ]
        verbose_name = "Resource Role"
        verbose_name_plural = "Resource Roles"

    def __str__(self):
        return f"{self.resource} -> {self.role}"
