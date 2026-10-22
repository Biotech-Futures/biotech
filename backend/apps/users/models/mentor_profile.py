from django.conf import settings
from django.db import models
from django.db.models import Q

class MentorProfile(models.Model):
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
