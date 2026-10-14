from django.conf import settings
from django.db import models
from django.db.models import Q

class MentorProfile(models.Model):
    # Exactly these five, in this order (AM2). Each label lowercases to its
    # key, so "HDR" and "hdr" name the same category.
    class BackgroundChoices(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        INDUSTRY = "industry", "Industry"
        UG = "undergraduate", "Undergraduate"
        PG = "postgraduate", "Postgraduate"
        HDR = "hdr", "HDR"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    background = models.CharField(max_length=50, choices=BackgroundChoices.choices, blank=True, null=True)
    institution = models.CharField(db_column='Institution', max_length=255)
    mentor_reason = models.TextField()
    max_group_count = models.PositiveIntegerField(default=3)

    class Meta:
        db_table = 'mentor_profile'
        verbose_name = "Mentor Profile"
        verbose_name_plural = "Mentor Profiles"
        constraints = [
            models.CheckConstraint(
                condition=Q(max_group_count__gte=0),
                name='mentor_max_group_count_non_negative'
            ),
        ]
    
    def __str__(self):
        return f"Mentor: {self.user}"


MENTOR_BACKGROUND_ERROR = "Mentor background must be one of: " + ", ".join(
    MentorProfile.BackgroundChoices.labels
)


def normalize_mentor_background(value):
    """Return the stored key for ``value``, or None when it is blank.

    Accepts a key or a label in any case ("Postgraduate", " HDR "). Raises
    ValueError for anything else, so callers can reject it rather than store
    free text the choices don't cover.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(MENTOR_BACKGROUND_ERROR)
    key = value.strip().lower()
    if not key:
        return None
    if key not in MentorProfile.BackgroundChoices.values:
        raise ValueError(MENTOR_BACKGROUND_ERROR)
    return key
