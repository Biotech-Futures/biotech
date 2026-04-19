from django.db import models

class EventTargetGroup(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    group = models.ForeignKey('groups.Groups', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_group'
        verbose_name = "Event Target Group"
        verbose_name_plural = "Event Target Groups"
        constraints = [
            models.UniqueConstraint(fields=['event', 'group'], name='unique_event_group')
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['group']),
        ]
    
    def __str__(self):
        return f"Target Group {self.group} for Event {self.event}"
