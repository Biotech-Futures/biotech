from django.conf import settings
from django.db import models


class Event(models.Model):
    """
    Represents a program event such as workshops or webinars.
    """

    TYPE_IN_PERSON = "in-person"
    TYPE_VIRTUAL = "virtual"

    TYPE_CHOICES = [
        (TYPE_IN_PERSON, "In Person"),
        (TYPE_VIRTUAL, "Virtual"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    long_description = models.TextField(blank=True)
    date = models.DateField()
    time = models.CharField(max_length=50)
    location = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    cover_image = models.URLField(blank=True, null=True)
    register_link = models.URLField(blank=True)
    capacity = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time", "id"]

    def __str__(self) -> str:
        return self.title


class EventRegistration(models.Model):
    """
    Associates a user with an event registration.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_registrations",
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        ordering = ["-registered_at"]

    def __str__(self) -> str:
        return f"{self.user} -> {self.event}"
