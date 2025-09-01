# RESOURCES & ROLES MODELS

from django.db import models

# Create your models here.

class ResourceRoles(models.Model):
    pk = models.CompositePrimaryKey('resource_id', 'role_id')
    resource_id = models.IntegerField(unique=True)
    role_id = models.IntegerField(unique=True)

    class Meta:
        # managed = False
        db_table = 'resource_roles'


class Resources(models.Model):
    resource = models.OneToOneField(ResourceRoles, models.DO_NOTHING, primary_key=True)
    resource_name = models.CharField(max_length=255, blank=True, null=True)
    resource_description = models.CharField(max_length=255)
    upload_datetime = models.DateTimeField()
    uploader_user_id_fk_field = models.IntegerField(db_column='uploader_user_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        # managed = False
        db_table = 'resources'

class RoleAssignmentHistory(models.Model):
    assignment_id = models.IntegerField(primary_key=True)
    # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    user_id_fk_field = models.OneToOneField(
        'Users', models.DO_NOTHING, db_column='user_id (FK)')
    # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    role_id_fk_field = models.OneToOneField(
        'Roles', models.DO_NOTHING, db_column='role_id (FK)')
    valid_from = models.DateTimeField(unique=True)
    valid_to = models.DateTimeField()

    class Meta:
        # managed = False
        db_table = 'role_assignment_history'


class Roles(models.Model):
    role = models.OneToOneField(
        EventTargetRole, models.DO_NOTHING, primary_key=True)
    role_name = models.CharField(unique=True, max_length=255)

    class Meta:
        # managed = False
        db_table = 'roles'