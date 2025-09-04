# SESSIONS MODELS

from django.db import models
from django.utils import timezone
from django.db.models import Q

class Sessions(models.Model):
    user = models.ForeignKey('users.Users', on_delete=models.CASCADE)
    access_datetime = models.DateTimeField(default=timezone.now)
    isloggedin = models.BooleanField(db_column='isLoggedin')  # Field name made lowercase.

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
            models.CheckConstraint(condition=Q(access_datetime__lte=timezone.now()),
                                   name="access_not_in_future"),
            # maybe have a constraint that ensures only one active session? eg check isLoggedIn
        ]

class Alerts(models.Model):
    session = models.ForeignKey('Sessions', on_delete=models.CASCADE)
    alert_timestamp = models.DateTimeField(default=timezone.now)
    error_reason = models.CharField(max_length=255)
    resolved = models.BooleanField(default=False)

    class Meta:
        db_table = 'alerts'
        verbose_name = "Alerts"
        ordering = ["-alert_timestamp"]
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['resolved'])
        ]
        constraints = [
            # no exact duplicates of alerts
            models.UniqueConstraint(
                fields=['session', 'alert_timestamp', 'error_reason'],
                name='unique_alert_user_session'
            ),
            # no empty reason for alert
            models.CheckConstraint(
                check=~Q(error_reason=''),
                name='alert_reason_not_empty'
            ),
        ]
