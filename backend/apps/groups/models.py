# GROUPS MODELS

from django.db import models

class Groups(models.Model):
    group = models.OneToOneField(EventTargetGroup, models.DO_NOTHING, primary_key=True)
    group_name = models.CharField(max_length=255)
    track_id_fk_field = models.ForeignKey('Tracks', models.DO_NOTHING, db_column='track_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    creation_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        # managed = False
        db_table = 'groups'

class GroupMembers(models.Model):
    pk = models.CompositePrimaryKey('group_id (FK)', 'user_id (FK)')
    group_id_fk_field = models.IntegerField(db_column='group_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    user_id_fk_field = models.IntegerField(db_column='user_id (FK)', unique=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'group_members'

class Tracks(models.Model):
    track = models.OneToOneField(EventTargetTrack, models.DO_NOTHING, primary_key=True)
    track_name = models.CharField(unique=True, max_length=255)
    state_id_fk_field = models.OneToOneField(CountryStates, models.DO_NOTHING, db_column='state_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'tracks'

class Countries(models.Model):
    country_id = models.IntegerField(primary_key=True)
    country_name = models.CharField(max_length=255)

    class Meta:
        # managed = False
        db_table = 'countries'

class CountryStates(models.Model):
    state_id = models.IntegerField(primary_key=True)
    country_id_fk_field = models.ForeignKey(Countries, models.DO_NOTHING, db_column='country_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    state_name = models.CharField(max_length=255)

    class Meta:
        # managed = False
        db_table = 'country_states'

