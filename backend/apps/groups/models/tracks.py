from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Tracks(models.Model):
    track_name = models.CharField(unique=True, max_length=255)
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by groups

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['track_name']),
        ]

    def __str__(self):
        return self.track_name
