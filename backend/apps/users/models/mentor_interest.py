from django.conf import settings
from django.db import models


class MentorInterest(models.Model):
    mentor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    interest = models.ForeignKey('AreasOfInterest', on_delete=models.CASCADE)

    class Meta:
        db_table = 'mentor_interest'
        verbose_name = "Mentor Interest"
        verbose_name_plural = "Mentor Interests"
        constraints = [
            models.UniqueConstraint(fields=['mentor_user', 'interest'], name='unique_mentor_interest')
        ]
        indexes = [
            models.Index(fields=['mentor_user']),
            models.Index(fields=['interest']),
        ]
