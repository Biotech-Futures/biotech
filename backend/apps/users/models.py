# USER MODELS

from django.db import models

class AdminProfile(models.Model):
    admin_id_fk_field = models.IntegerField(db_column='admin_id (FK)', primary_key=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    """ 
    OneToOneField may be better than storing an integer for a foreign key - this allows django to know about the relationship with the user. gives us things like auto joins, cascade deletes and validation
    e.g. 
    admin = models.OneToOneField(
        UserModel,  # or your Admin model
        on_delete=models.CASCADE,
        db_column='admin_id (FK)',  # optional if you need to map existing DB column
        primary_key=True
    )

    this means each AdminProfile maps to one Admin (which is a user)
    """

    class Meta:
        # managed = False
        db_table = 'admin_profile'


class AreasOfInterest(models.Model):
    interest_id = models.IntegerField(primary_key=True)
    interest_desc = models.CharField(max_length=255)

    class Meta:
        # managed = False
        db_table = 'areas_of_interest'


class Background(models.Model):
    background_id = models.IntegerField(primary_key=True)
    background_desc_unique_field = models.CharField(db_column='background_desc (UNIQUE)', unique=True, max_length=255)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        # managed = False
        db_table = 'background'

class MentorProfile(models.Model):
    user_id_fk_field = models.IntegerField(db_column='user_id (FK)', primary_key=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    background_id_fk_field = models.ForeignKey(Background, models.DO_NOTHING, db_column='background_id(FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    institution = models.CharField(db_column='Institution', max_length=255)  # Field name made lowercase.
    mentor_reason = models.CharField(max_length=255)
    max_grp_cnt = models.IntegerField()

    class Meta:
        # managed = False
        db_table = 'mentor_profile'

class RelationshipType(models.Model):
    relationship_type_id = models.IntegerField(primary_key=True)
    relationship_type = models.CharField(unique=True, max_length=255)

    class Meta:
        # managed = False
        db_table = 'relationship_type'

class StudentInterest(models.Model):
    pk = models.CompositePrimaryKey('interest_id', 'user_id')
    interest_id = models.IntegerField(unique=True)
    user_id = models.IntegerField(unique=True)

    class Meta:
        # managed = False
        db_table = 'student_interest'


class StudentProfile(models.Model):
    user_id_fk_field = models.OneToOneField('StudentSupervisor', models.DO_NOTHING, db_column='user_id (FK)', primary_key=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.CharField(max_length=255)
    supervisor_id_fk_field = models.ForeignKey('SupervisorProfile', models.DO_NOTHING, db_column='supervisor_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    interest_id_fk_field = models.ForeignKey(AreasOfInterest, models.DO_NOTHING, db_column='interest_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'student_profile'


class StudentSupervisor(models.Model):
    pk = models.CompositePrimaryKey('student_user_id', 'supervisor_user_id')
    student_user_id = models.IntegerField(unique=True)
    supervisor_user_id = models.IntegerField(unique=True)
    relationship_type = models.ForeignKey(RelationshipType, models.DO_NOTHING)

    class Meta:
        # managed = False
        db_table = 'student_supervisor'


class SupervisorProfile(models.Model):
    user_id_fk_field = models.OneToOneField(StudentSupervisor, models.DO_NOTHING, db_column='user_id(FK)', primary_key=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    school_name = models.CharField(max_length=255)

    class Meta:
        # managed = False
        db_table = 'supervisor_profile'

class Users(models.Model):
    user = models.OneToOneField('WorkshopAttendance', models.DO_NOTHING, primary_key=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    status = models.BooleanField()
    track = models.ForeignKey(Tracks, models.DO_NOTHING)
    state = models.ForeignKey(CountryStates, models.DO_NOTHING)

    class Meta:
        # managed = False
        db_table = 'users'