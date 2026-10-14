from django.db import models
from django.db.models.functions import Lower


class KnownUniversity(models.Model):
    """Admin-maintained university aliases used by registration validation."""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "known_university"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="known_university_name_unique"),
        ]

    @staticmethod
    def normalise(name):
        return " ".join(str(name or "").split())

    @classmethod
    def matches(cls, school_name):
        name = cls.normalise(school_name)
        return bool(name) and cls.objects.filter(name__iexact=name).exists()

    def save(self, *args, **kwargs):
        self.name = self.normalise(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
