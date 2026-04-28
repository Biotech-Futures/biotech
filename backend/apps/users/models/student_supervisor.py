from django.conf import settings
from django.db import models
from django.db.models import Q, F

class StudentSupervisor(models.Model):
    class RelationshipTypeChoices(models.TextChoices):
        TEACHER = "teacher", "Teacher"
        PARENT_GUARDIAN = "parent_guardian", "Parent/Guardian"
        OTHER = "other", "Other (Specify)"

    student_user = models.ForeignKey('StudentProfile', on_delete=models.CASCADE)
    supervisor_user = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, null=True)
    relationship_type = models.CharField(max_length=50, choices=RelationshipTypeChoices.choices, default=RelationshipTypeChoices.OTHER)

    class Meta:
        db_table = 'student_supervisor'
        verbose_name = "Student Supervisor"
        verbose_name_plural = "Student Supervisors"
        indexes = [
            models.Index(fields=['student_user']),
            models.Index(fields=['supervisor_user']),
        ]

        constraints = [
            models.UniqueConstraint(fields=['student_user', 'supervisor_user'], name='pk_student_supervisor'),
            models.CheckConstraint(condition=~Q(student_user=None), name='student_user_not_null'),
            models.CheckConstraint(condition=Q(supervisor_user__isnull=True) | ~Q(student_user=F('supervisor_user')), name='no_self_supervision'),
        ]
    
    def __str__(self):
        return f"{self.student_user} -> {self.supervisor_user}"
