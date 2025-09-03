# USER MODELS

from django.db import models

class AdminProfile(models.Model):
    admin = models.OneToOneField('Users', models.DO_NOTHING, primary_key=True)

    class Meta:
        db_table = 'admin_profile'

class AreasOfInterest(models.Model):
    interest_id = models.IntegerField(primary_key=True)
    interest_desc = models.CharField(max_length=255)

    class Meta:
        db_table = 'areas_of_interest'

class Background(models.Model):
    background_id = models.IntegerField(primary_key=True)
    background_desc_unique_field = models.CharField(db_column='background_desc (UNIQUE)', unique=True, max_length=255)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        db_table = 'background'














class MentorProfile(models.Model):
    user = models.OneToOneField('Users', models.DO_NOTHING, primary_key=True)
    background = models.ForeignKey(Background, models.DO_NOTHING)
    institution = models.CharField(db_column='Institution', max_length=255)  # Field name made lowercase.
    mentor_reason = models.CharField(max_length=255)
    max_grp_cnt = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'mentor_profile'






class RelationshipType(models.Model):
    relationship_type_id = models.IntegerField(primary_key=True)
    relationship_type = models.CharField(unique=True, max_length=255)

    class Meta:
        managed = False
        db_table = 'relationship_type'





class StudentInterest(models.Model):
    pk = models.CompositePrimaryKey('interest_id', 'user_id')
    interest_id = models.IntegerField(unique=True)
    user = models.ForeignKey('Users', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'student_interest'


class StudentProfile(models.Model):
    user = models.OneToOneField('Users', models.DO_NOTHING, primary_key=True)
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.CharField(max_length=255)
    supervisor = models.ForeignKey('SupervisorProfile', models.DO_NOTHING)
    interest = models.ForeignKey(AreasOfInterest, models.DO_NOTHING)
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'student_profile'


class StudentSupervisor(models.Model):
    pk = models.CompositePrimaryKey('student_user_id', 'supervisor_user_id')
    student_user = models.ForeignKey(StudentProfile, models.DO_NOTHING)
    supervisor_user = models.ForeignKey('SupervisorProfile', models.DO_NOTHING)
    relationship_type = models.ForeignKey(RelationshipType, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'student_supervisor'


class SupervisorProfile(models.Model):
    user = models.OneToOneField('Users', models.DO_NOTHING, primary_key=True)
    school_name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'supervisor_profile'



class Users(models.Model):
    user_id = models.IntegerField(primary_key=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    status = models.BooleanField()
    track = models.ForeignKey(Tracks, models.DO_NOTHING)
    state = models.ForeignKey(CountryStates, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'users'