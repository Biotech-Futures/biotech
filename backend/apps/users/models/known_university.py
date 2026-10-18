from django.db import models
from django.db.models.functions import Lower


class KnownUniversity(models.Model):
    """A name registration treats as a university rather than a school, e.g.
    "USYD". Kept by admins in Django admin; a student whose school name matches
    one (ignoring case and spacing) is asked to confirm it before registering.
    Names containing "university" are caught without being listed."""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'known_university'
        verbose_name = "Known University"
        verbose_name_plural = "Known Universities"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='known_university_name_unique'),
        ]

    @staticmethod
    def normalise(name) -> str:
        """The name with outer and repeated spaces removed, as it is stored."""
        return " ".join(str(name or "").split())

    @classmethod
    def matches(cls, school_name) -> bool:
        name = cls.normalise(school_name)
        return bool(name) and cls.objects.filter(name__iexact=name).exists()

    def save(self, *args, **kwargs):
        self.name = self.normalise(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
