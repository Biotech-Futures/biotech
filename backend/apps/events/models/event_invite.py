from django.conf import settings
from django.db import models
from django.utils import timezone

class EventInvite(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # changed to CASCADE to maintain referential integrity
    sent_datetime = models.DateTimeField(default=timezone.now)
    attendance_status = models.BooleanField(default=False) # changed to default False to avoid null values
    rsvp_status = models.BooleanField(default=False) # changed to default False to avoid null values

    class Meta:
        db_table = 'event_invite'
        verbose_name = "Event Invite"
        verbose_name_plural = "Event Invites"
        constraints = [
            models.UniqueConstraint(fields=['event', 'user'], name='unique_event_user'), # composite key equivalent; Django adds a default id

            # Ensure attendance can only be True if RSVP is also True
            models.CheckConstraint(
                condition=models.Q(attendance_status=False) | models.Q(rsvp_status=True),
                name='check_attendance_requires_rsvp'
            ),
            models.CheckConstraint(
                condition=models.Q(sent_datetime__lte=models.functions.Now()),
                name='check_invite_sent_datetime_not_future'
            )
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Invite for {self.user} to {self.event}"
