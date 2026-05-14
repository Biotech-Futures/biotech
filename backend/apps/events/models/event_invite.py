from django.conf import settings
from django.db import models


class EventRsvp(models.Model):
    # RSVP statuses use the meeting-standard wording (Outlook / Google
    # Calendar / iCalendar PARTSTAT) so the API matches what every
    # other surface in the product already calls these states.
    class RsvpStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        TENTATIVE = "tentative", "Tentative"
        DECLINED = "declined", "Declined"
        # WAITLISTED = "the user wanted ACCEPTED but the event was at
        # capacity". Auto-promoted to ACCEPTED when an accepted user
        # leaves the event (see services.set_user_rsvp).
        WAITLISTED = "waitlisted", "Waitlisted"

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
            # responded_at is only meaningful once the user has actually
            # responded (anything other than PENDING). WAITLISTED counts
            # as a response — the user took an action, the system held
            # back the slot.
            models.CheckConstraint(
                condition=models.Q(responded_at__isnull=True)
                | models.Q(
                    rsvp_status__in=[
                        "accepted",
                        "tentative",
                        "declined",
                        "waitlisted",
                    ]
                ),
                name="event_rsvp_response_state_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["user"]),
            models.Index(fields=["rsvp_status"]),
            # Powers the waitlist-promotion lookup (oldest WAITLISTED per
            # event by responded_at) plus the per-event accepted/waitlist
            # COUNT annotations on the list endpoint.
            models.Index(
                fields=["event", "rsvp_status", "responded_at"],
                name="evrsvp_evt_stat_resp_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} -> {self.event} ({self.rsvp_status})"


EventInvite = EventRsvp