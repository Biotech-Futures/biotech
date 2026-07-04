from django.conf import settings
from django.db import models

class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    school_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'supervisor_profile'
        verbose_name = "Supervisor Profile"
        verbose_name_plural = "Supervisor Profiles"

    def __str__(self):
        return str(self.user)
