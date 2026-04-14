from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class ResourceType(models.Model):
    type_name = models.CharField(max_length=50, unique=True)
    type_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'resource_types'
        verbose_name = "Resource Type"
        verbose_name_plural = "Resource Types"

    def __str__(self):
        return self.type_name
