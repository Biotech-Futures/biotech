from django.conf import settings
from django.db import models
from django.db.models import Q

class MentorProfile(models.Model):
    # Exactly these five, in this order (AM2). Each label lowercases to its
    # key, so "HDR" and "hdr" name the same category.
    class BackgroundChoices(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        INDUSTRY = "industry", "Industry"
        UG = "undergraduate", "University Student – Undergraduate"
        PG = "postgraduate", "University Student – Postgraduate"
        HDR = "hdr", "University Student – HDR"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    background = models.CharField(max_length=50, choices=BackgroundChoices.choices, blank=True, null=True)
    institution = models.CharField(db_column='Institution', max_length=255)
    mentor_reason = models.TextField()
    max_group_count = models.PositiveIntegerField(default=3)
    # From registering (apps.users.registration_intake): where an industry
    # mentor works; a university student's year ("1" to "4", or "5+"); and a
    # student's or academic's field of study or research.
    company = models.CharField(max_length=255, blank=True, default="")
    university_year = models.CharField(max_length=8, blank=True, default="")
    field_of_study = models.CharField(max_length=255, blank=True, default="")
    # No longer asked, shown or changed (relevant background, how they'd
    # mentor BIOTech groups, hours a week): kept for what earlier mentors gave.
    relevant_background = models.TextField(blank=True, default="")
    mentoring_approach = models.TextField(blank=True, default="")
    weekly_hours = models.PositiveSmallIntegerField(blank=True, null=True)

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
    if key in MentorProfile.BackgroundChoices.values:
        return key
    # A label no longer lowercases to its key ("University Student –
    # Undergraduate"), so match the labels explicitly rather than relying on
    # the two happening to coincide.
    for choice_key, label in MentorProfile.BackgroundChoices.choices:
        if label.lower() == key:
            return choice_key
    raise ValueError(MENTOR_BACKGROUND_ERROR)
