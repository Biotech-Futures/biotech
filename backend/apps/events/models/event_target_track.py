from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

class EventTargetTrack(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    track = models.ForeignKey('groups.Tracks', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_track'
        verbose_name = "Event Target Track"
        verbose_name_plural = "Event Target Tracks"
        constraints = [
            models.UniqueConstraint(fields=['event', 'track'], name='unique_event_track')
        ]
    
    def __str__(self):
        return f"{self.track} targeted for {self.event}"
