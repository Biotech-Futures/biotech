# EVENTS MODELS

from django.db import models

class EventInvite(models.Model):
    pk = models.CompositePrimaryKey('event_id', 'user_id')
    event = models.ForeignKey('Events', models.DO_NOTHING)
    user = models.ForeignKey('Users', models.DO_NOTHING)
    sent_datetime = models.DateTimeField()
    attendance_status = models.BooleanField()
    rsvp_status = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'event_invite'

class EventTargetGroup(models.Model):
    pk = models.CompositePrimaryKey('event_id', 'group_id')
    event = models.ForeignKey('Events', models.DO_NOTHING)
    group = models.ForeignKey('Groups', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'event_target_group'

class EventTargetRole(models.Model):
    pk = models.CompositePrimaryKey('event_id', 'role_id')
    event = models.ForeignKey('Events', models.DO_NOTHING)
    role = models.ForeignKey('Roles', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'event_target_role'

class EventTargetTrack(models.Model):
    pk = models.CompositePrimaryKey('event_id', 'track_id')
    event = models.ForeignKey('Events', models.DO_NOTHING)
    track = models.ForeignKey('Tracks', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'event_target_track'

class Events(models.Model):
    event_id = models.IntegerField(primary_key=True)
    event_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)
    humanitix_link = models.CharField(max_length=255)
    host_user = models.ForeignKey('Users', models.DO_NOTHING)
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()
    event_image_img_field = models.CharField(db_column='event_image(IMG)', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.     
    is_virtual = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'events'