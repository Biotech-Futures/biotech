from django.conf import settings
from django.db import models
from django.db.models import Q

class MentorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    institution = models.CharField(db_column='Institution', max_length=255)
    mentor_reason = models.CharField(max_length=255)
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
