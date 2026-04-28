from django.conf import settings
from django.db import models


class EventRsvp(models.Model):
    class RsvpStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        GOING = "going", "Going"
        MAYBE = "maybe", "Maybe"
        DECLINED = "declined", "Declined"

    event = models.ForeignKey("Events", on_delete=models.CASCADE, related_name="rsvps")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rsvp_status = models.CharField(
        max_length=50,
        choices=RsvpStatus.choices,
        default=RsvpStatus.PENDING,
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "event_rsvp"
        verbose_name = "Event RSVP"
        verbose_name_plural = "Event RSVPs"
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_event_rsvp_user"),
            models.CheckConstraint(
                condition=models.Q(responded_at__isnull=True)
                | models.Q(rsvp_status__in=["going", "maybe", "declined"]),
                name="event_rsvp_response_state_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["user"]),
            models.Index(fields=["rsvp_status"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.event} ({self.rsvp_status})"


EventInvite = EventRsvp
