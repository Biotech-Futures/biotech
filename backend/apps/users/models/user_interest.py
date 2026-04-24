from django.conf import settings
from django.db import models

class UserInterest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    interest = models.ForeignKey('AreasOfInterest', on_delete=models.CASCADE)

    class Meta:
        db_table = 'user_interest'
        verbose_name = "User Interest"
        verbose_name_plural = "User Interests"
        constraints = [
            models.UniqueConstraint(fields=['user', 'interest'], name='pk_user_interest')
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['interest']),
        ]

    def __str__(self):
        return f"{self.user} interested in {self.interest}"
