from django.db import models


class ResourceRelease(models.Model):
    """When a resource was released in a year (Sydney time): shown, or its
    release date come. Next year's Release Resources sorts by it (Last
    released). One a year, the first; a date set ahead is kept until it comes."""

    resource = models.ForeignKey("Resources", on_delete=models.CASCADE, related_name="releases")
    year = models.PositiveSmallIntegerField()
    released_at = models.DateTimeField()

    class Meta:
        db_table = "resource_release"
        constraints = [
            models.UniqueConstraint(fields=["resource", "year"], name="resource_release_once_a_year"),
        ]

    def __str__(self):
        return f"{self.resource_id} released {self.released_at:%Y-%m-%d} ({self.year})"
