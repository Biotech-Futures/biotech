from django.db import models


class Resource(models.Model):
    """
    Represents a downloadable resource (document, video, template, guide)
    stored in object storage and optionally associated with a cover image.
    """

    TYPE_DOCUMENT = "document"
    TYPE_VIDEO = "video"
    TYPE_TEMPLATE = "template"
    TYPE_GUIDE = "guide"

    ROLE_ALL = "all"
    ROLE_STUDENT = "student"
    ROLE_MENTOR = "mentor"
    ROLE_SUPERVISOR = "supervisor"
    ROLE_ADMIN = "admin"

    TYPE_CHOICES = [
        (TYPE_DOCUMENT, "Document"),
        (TYPE_VIDEO, "Video"),
        (TYPE_TEMPLATE, "Template"),
        (TYPE_GUIDE, "Guide"),
    ]

    ROLE_CHOICES = [
        (ROLE_ALL, "All Users"),
        (ROLE_STUDENT, "Student"),
        (ROLE_MENTOR, "Mentor"),
        (ROLE_SUPERVISOR, "Supervisor"),
        (ROLE_ADMIN, "Admin"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ALL)
    file_url = models.URLField()
    cover_image = models.URLField(blank=True, null=True)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
