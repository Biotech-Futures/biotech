from django.db import models


class Announcement(models.Model):
    """
    Stores broadcast announcements targeted to specific audiences.
    """

    AUDIENCE_ALL = "all"
    AUDIENCE_STUDENT = "student"
    AUDIENCE_MENTOR = "mentor"
    AUDIENCE_SUPERVISOR = "supervisor"
    AUDIENCE_ADMIN = "admin"

    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, "All Users"),
        (AUDIENCE_STUDENT, "Student"),
        (AUDIENCE_MENTOR, "Mentor"),
        (AUDIENCE_SUPERVISOR, "Supervisor"),
        (AUDIENCE_ADMIN, "Admin"),
    ]

    title = models.CharField(max_length=255)
    summary = models.TextField()
    content = models.TextField(blank=True)
    author = models.CharField(max_length=100, default="Program Team")
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    link = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.title
