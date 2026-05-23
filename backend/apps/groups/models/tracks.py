from django.db import models

class Tracks(models.Model):
    track_name = models.CharField(unique=True, max_length=100)
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return self.track_name
