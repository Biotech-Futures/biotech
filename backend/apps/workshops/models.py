# WORKSHOPS MODELS

from django.db import models

class WorkshopAttendance(models.Model):
    pk = models.CompositePrimaryKey('workshop_id', 'user_id')
    workshop = models.OneToOneField('Workshops', models.DO_NOTHING)
    user = models.ForeignKey(Users, models.DO_NOTHING)
    responded = models.BooleanField()

    class Meta:
        db_table = 'workshop_attendance'

class Workshops(models.Model):
    workshop_id = models.IntegerField(primary_key=True)
    workshop_name = models.CharField(max_length=255)
    start_datetime = models.DateTimeField()
    duration = models.DateTimeField()
    location = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    zoom_link = models.CharField(max_length=255, blank=True, null=True)
    host_user = models.ForeignKey(Users, models.DO_NOTHING)
    group = models.ForeignKey(Groups, models.DO_NOTHING)
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        db_table = 'workshops'