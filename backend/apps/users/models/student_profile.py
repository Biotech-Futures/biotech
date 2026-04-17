from django.conf import settings
from django.db import models
from django.db.models import Q

class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.BooleanField(default=False) 
    supervisor = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, blank=True, null=True)
    interest = models.ForeignKey('AreasOfInterest', on_delete=models.SET_NULL, blank=True, null=True)
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField(default=False)
    joinperm_responseID = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = 'student_profile'
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['supervisor']),
            models.Index(fields=['interest']),
        ]
        constraints = [
        models.CheckConstraint(
            condition=~Q(pg_first_name=''),
            name='student_first_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(pg_last_name=''),
            name='student_last_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(school_name=''),
            name='student_school_name_not_empty'
        ),
        models.CheckConstraint(
            condition=Q(year_lvl__in=[str(i) for i in range(9, 13)]),
            name='student_year_lvl_valid'
        ),
        models.CheckConstraint(
            condition=Q(has_join_permission=False) | Q(parent_guardian_flag=True),
            name='permission_requires_parent_guardian'
        )
        ]

    def __str__(self):
        return str(self.user)
