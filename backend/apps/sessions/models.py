# SESSIONS MODELS

from django.db import models

class Sessions(models.Model):
    session_id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING)
    access_datetime = models.DateTimeField()
    isloggedin = models.BooleanField(db_column='isLoggedin')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'sessions'

class Alerts(models.Model):
    alert_id = models.BigIntegerField(primary_key=True)
    session = models.ForeignKey('Sessions', models.DO_NOTHING)
    alert_timestamp = models.DateTimeField()
    error_reason = models.CharField(max_length=255)
    resolved = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'alerts'
