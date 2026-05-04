from django.db import models
from django.conf import settings


class MatchRun(models.Model):
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='admin_match_runs',
    )
    run_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField()

    class Meta:
        db_table = 'admin_match_run'
