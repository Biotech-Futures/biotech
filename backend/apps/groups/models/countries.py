from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Countries(models.Model):
    country_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'countries'
        indexes = [
            models.Index(fields=['country_name']),
        ]

    def __str__(self):
        return self.country_name
