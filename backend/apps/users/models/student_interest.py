from django.conf import settings
from django.db import models

class StudentInterest(models.Model):
    interest = models.ForeignKey('AreasOfInterest', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'student_interest'
        verbose_name = "Student Interest"
        verbose_name_plural = "Student Interests"
        constraints = [
            models.UniqueConstraint(fields=['interest', 'user'], name='pk_student_interest')
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['interest']),
        ]

    def __str__(self):
        return f"{self.user} interested in {self.interest}"
