from django.conf import settings
from django.db import models
from django.db.models import Q


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.BooleanField(default=False)
    supervisor = models.ForeignKey(
        "SupervisorProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    year_level = models.PositiveSmallIntegerField(blank=True, null=True)
    join_permission_received = models.BooleanField(default=False)
    join_permission_response_id = models.CharField(max_length=255, null=True, blank=True)
    country = models.ForeignKey(
        "groups.Countries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
    )
    state = models.ForeignKey(
        "groups.CountryStates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
    )
    preassigned_group = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        db_table = "student_profile"
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=["supervisor"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(pg_first_name=""),
                name="student_first_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(pg_last_name=""),
                name="student_last_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(school_name=""),
                name="student_school_name_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(year_lvl__in=[str(i) for i in range(9, 13)]),
                name="student_year_lvl_valid",
            ),
            models.CheckConstraint(
                condition=Q(join_permission_received=False) | Q(parent_guardian_flag=True),
                name="permission_requires_parent_guardian",
            ),
        ]

    def __str__(self):
        return str(self.user)
