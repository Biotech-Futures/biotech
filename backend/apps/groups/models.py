# GROUPS MODELS

from django.db import models

class GroupMembers(models.Model):
    pk = models.CompositePrimaryKey('group_id', 'user_id')
    group = models.ForeignKey('Groups', models.DO_NOTHING)
    user = models.ForeignKey('Users', models.DO_NOTHING)

    class Meta:
        db_table = 'group_members'

class Groups(models.Model):
    group_id = models.IntegerField(primary_key=True)
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey('Tracks', models.DO_NOTHING)
    creation_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        db_table = 'groups'

class Tracks(models.Model):
    track_id = models.IntegerField(primary_key=True)
    track_name = models.CharField(unique=True, max_length=255)
    state = models.OneToOneField(CountryStates, models.DO_NOTHING)

    class Meta:
        db_table = 'tracks'

class Countries(models.Model):
    country_id = models.IntegerField(primary_key=True)
    country_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'countries'

class CountryStates(models.Model):
    state_id = models.IntegerField(primary_key=True)
    country = models.ForeignKey(Countries, models.DO_NOTHING)
    state_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'country_states'

