from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class KnownUniversity(models.Model):
    """A university registration treats as one rather than a school: a
    student whose school name matches its full name or acronym (ignoring case
    and spacing) is asked to confirm it before registering. Names containing
    "university" are caught without being listed."""

    full_name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=64, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'known_university'
        verbose_name = "Known University"
        verbose_name_plural = "Known Universities"
        ordering = ['full_name']
        constraints = [
            models.UniqueConstraint(Lower('full_name'), name='known_university_full_name_unique'),
        ]
        indexes = [
            models.Index(Lower('acronym'), name='known_university_acronym_lower'),
        ]

    @staticmethod
    def normalise(name) -> str:
        """The name with outer and repeated spaces removed, as it is stored."""
        return " ".join(str(name or "").split())

    @classmethod
    def matching(cls, school_names) -> set:
        """Which of ``school_names`` (normalised, lower case) are a listed full
        name or acronym, in one query."""
        keys = {cls.normalise(name).lower() for name in school_names} - {""}
        if not keys:
            return set()
        found = set()
        rows = (
            cls.objects.annotate(full_key=Lower('full_name'), acronym_key=Lower('acronym'))
            .filter(Q(full_key__in=keys) | Q(acronym_key__in=keys))
            .values_list('full_key', 'acronym_key')
        )
        for full_key, acronym_key in rows:
            found.update((full_key, acronym_key))
        return keys & found

    @classmethod
    def matches(cls, school_name) -> bool:
        return bool(cls.matching([school_name]))

    def save(self, *args, **kwargs):
        self.full_name = self.normalise(self.full_name)
        self.acronym = self.normalise(self.acronym)
        self.country = self.normalise(self.country)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.acronym})" if self.acronym else self.full_name
