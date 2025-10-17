# SESSIONS MODELS
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import Now

class Sessions(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_datetime = models.DateTimeField(default=timezone.now)
    isloggedin = models.BooleanField(db_column='isLoggedin')  

    class Meta:
        db_table = 'sessions'
        verbose_name = "Sessions"
        ordering = ["-access_datetime"]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['access_datetime'])
        ]
        constraints = [
            # no same sessions
            models.UniqueConstraint(fields=["user", "access_datetime"], name="unique_user_session"),
            # check a session is not in future
            models.CheckConstraint(condition=Q(access_datetime__lte=Now()),
                                   name="access_not_in_future"),
        ]
    def __str__(self):
        return f"Session for {self.user} at {self.access_datetime}"

class Alerts(models.Model):
    session = models.ForeignKey('Sessions', on_delete=models.CASCADE, related_name="alerts")
    alert_timestamp = models.DateTimeField(default=timezone.now)
    error_reason = models.CharField(max_length=255)
    resolved = models.BooleanField(default=False)

    class Meta:
        db_table = 'alerts'
        verbose_name = "Alerts"
        ordering = ["-alert_timestamp"]
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['resolved']),
            models.Index(fields=['alert_timestamp'])
        ]
        constraints = [
            # no exact duplicates of alerts
            models.UniqueConstraint(
                fields=['session', 'alert_timestamp', 'error_reason'],
                name='unique_alert_user_session'
            ),
            # no empty reason for alert
            models.CheckConstraint(
                condition=~Q(error_reason=''),
                name='alert_reason_not_empty'
            ),
        ]
    def __str__(self):
        return f"Alert for {self.session} at {self.alert_timestamp}: {self.error_reason}"
