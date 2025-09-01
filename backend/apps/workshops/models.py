# WORKSHOPS MODELS

from django.db import models

class Workshops(models.Model):
    workshop = models.OneToOneField(WorkshopAttendance, models.DO_NOTHING, primary_key=True)
    workshop_name = models.CharField(max_length=255)
    start_datetime = models.DateTimeField()
    duration = models.DateTimeField()
    location = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    zoom_link = models.CharField(max_length=255, blank=True, null=True)
    host_user_id_fk_field = models.ForeignKey(Users, models.DO_NOTHING, db_column='host_user_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    group_id_fk_field = models.ForeignKey(Groups, models.DO_NOTHING, db_column='group_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        # managed = False
        db_table = 'workshops'

class WorkshopAttendance(models.Model):
    pk = models.CompositePrimaryKey('workshop_id', 'user_id (FK)')
    workshop_id = models.IntegerField(unique=True)
    user_id_fk_field = models.IntegerField(db_column='user_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    responded = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'workshop_attendance'