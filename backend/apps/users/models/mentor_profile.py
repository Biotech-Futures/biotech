from django.conf import settings
from django.db import models
from django.db.models import Q


class MentorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    institution = models.CharField(max_length=255, blank=True, null=True)
    mentor_reason = models.CharField(max_length=255, blank=True, default="")
    max_group_count = models.PositiveIntegerField(default=3)
    country = models.ForeignKey(
        "groups.Countries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentor_profiles",
    )
    state = models.ForeignKey(
        "groups.CountryStates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentor_profiles",
    )
    background = models.CharField(max_length=120, blank=True, default="")
    region = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        db_table = "mentor_profile"
        verbose_name = "Mentor Profile"
        verbose_name_plural = "Mentor Profiles"
        constraints = [
            models.CheckConstraint(
                condition=Q(max_group_count__gte=0),
                name="mentor_max_group_count_non_negative",
            ),
        ]

    def __str__(self):
        return f"Mentor: {self.user}"
