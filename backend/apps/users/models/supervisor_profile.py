from django.conf import settings
from django.db import models

class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    school_name = models.CharField(max_length=255, null=True, blank=True)
    # The supervisor's own order for their groups on My Groups, as group ids.
    # Groups not in it follow, by name.
    group_order = models.JSONField(default=list, blank=True)
    # Still registers students while registration is closed by its dates
    # (Management > Late Registration > Supervisors After Close).
    register_after_close = models.BooleanField(default=False)
    # The day their weekly registration status email last went, so it goes
    # once a week at most (apps.users.supervisor_status).
    status_digest_sent_on = models.DateField(null=True, blank=True)
    # How their students without a group are matched, asked at the top of My
    # Groups: "school_only", "cross_school", or "" until they answer. Start
    # new year clears it.
    grouping_preference = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        db_table = 'supervisor_profile'
        verbose_name = "Supervisor Profile"
        verbose_name_plural = "Supervisor Profiles"

    def __str__(self):
        return str(self.user)
