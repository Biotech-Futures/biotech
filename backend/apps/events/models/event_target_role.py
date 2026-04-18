from django.db import models

class EventTargetRole(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    role = models.ForeignKey('resources.Roles', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_role'
        verbose_name = "Event Target Role"
        verbose_name_plural = "Event Target Roles"
        constraints = [
            models.UniqueConstraint(fields=['event', 'role'], name='unique_event_role')
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"Target Role {self.role} for Event {self.event}"
