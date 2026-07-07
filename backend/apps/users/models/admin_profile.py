from django.conf import settings
from django.db import models
from django.db.models import Q, F


class AdminProfile(models.Model):
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    banned = models.BooleanField(default=False)
    ban_reason = models.TextField(null=True, blank=True)
    ban_expires = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'admin_profile'
        verbose_name = "Admin Profile"
        verbose_name_plural = "Admin Profiles"

    def __str__(self):
        return str(self.admin)
