from django.conf import settings
from django.db import models

class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    school_name = models.CharField(max_length=255, null=True, blank=True)
    # The supervisor's own order for their groups on My Groups, as group ids.
    # Groups not in it follow, by name.
    group_order = models.JSONField(default=list, blank=True)
    # Still registers students while registration is closed by its dates
    # (Management > Registration Visibility > Supervisors After Close).
    register_after_close = models.BooleanField(default=False)

    class Meta:
        db_table = 'supervisor_profile'
        verbose_name = "Supervisor Profile"
        verbose_name_plural = "Supervisor Profiles"

    def __str__(self):
        return str(self.user)
