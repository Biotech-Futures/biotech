# SESSIONS MODELS

from django.db import models

class Sessions(models.Model):
    session_id = models.IntegerField(primary_key=True)
    # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    user_id_fk_field = models.ForeignKey(
        'Users', models.DO_NOTHING, db_column='user_id (FK)')
    access_datetime = models.DateTimeField()
    # Field name made lowercase.
    isloggedin = models.BooleanField(db_column='isLoggedin')

    class Meta:
        # managed = False
        db_table = 'sessions'

class Alerts(models.Model):
    alert_id = models.BigIntegerField(primary_key=True)
    session_id_fk_field = models.ForeignKey('Sessions', models.DO_NOTHING, db_column='session_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    alert_timestamp = models.DateTimeField()
    error_reason = models.CharField(max_length=255)
    resolved = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'alerts'
