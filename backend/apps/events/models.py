# EVENTS MODELS

from django.db import models

class EventTargetRole(models.Model):
    pk = models.CompositePrimaryKey('event_id (FK)', 'role_id (FK)')
    event_id_fk_field = models.IntegerField(db_column='event_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    role_id_fk_field = models.IntegerField(db_column='role_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'event_target_role'

class Events(models.Model):
    event = models.OneToOneField(EventTargetRole, models.DO_NOTHING, primary_key=True)
    event_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)
    humanitix_link = models.CharField(max_length=255)
    host_user_id_fk_field = models.ForeignKey('Users', models.DO_NOTHING, db_column='host_user_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()
    event_image_img_field = models.CharField(db_column='event_image(IMG)', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    is_virtual = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'events'

class EventInvite(models.Model):
    pk = models.CompositePrimaryKey('event_id (FK)', 'user_id (FK)')
    event_id_fk_field = models.IntegerField(db_column='event_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    user_id_fk_field = models.IntegerField(db_column='user_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    sent_datetime = models.DateTimeField()
    attendance_status = models.BooleanField()
    rsvp_status = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'event_invite'

class EventTargetGroup(models.Model):
    pk = models.CompositePrimaryKey('event_id (FK)', 'group_id (FK)')
    event_id_fk_field = models.IntegerField(db_column='event_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    group_id_fk_field = models.IntegerField(db_column='group_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'event_target_group'



class EventTargetTrack(models.Model):
    pk = models.CompositePrimaryKey('event_id (FK)', 'track_id (FK)')
    event_id_fk_field = models.IntegerField(db_column='event_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    track_id_fk_field = models.IntegerField(db_column='track_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'event_target_track'

"""
FOR EventInvite, EventTargetGroup, EventTargetRole, EventTargetTrack

GPT says to sack the CompositePrimaryKey subclass as Django doesn't actually support it - and using unique=True on the foreign keys leads to incorrect behaviour and turns the join into multiple one-to-one
relationships. It says to use a surrogate PK and then enforce a unique constraint across both FKs - and don't use IntegerField, but rather use models.ForeignKey.

e.g.
class Event(models.Model):
    name = models.CharField(max_length=100)

class User(models.Model):
    username = models.CharField(max_length=100)

class EventInvite(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(default=now())

    class Meta:
        unique_together = ('event', 'user') # this ensures that event + user (our composite key) is unique together

this comment also applied for anywhere else we use IntegerField - almost all of the models.
"""

