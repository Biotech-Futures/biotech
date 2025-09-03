# RESOURCES & ROLES MODELS

from django.db import models

class ResourceRoles(models.Model):
    pk = models.CompositePrimaryKey('resource_id', 'role_id')
    resource = models.OneToOneField('Resources', models.DO_NOTHING)
    role = models.ForeignKey('Roles', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'resource_roles'

class Resources(models.Model):
    resource_id = models.IntegerField(primary_key=True)
    resource_name = models.CharField(max_length=255, blank=True, null=True)
    resource_description = models.CharField(max_length=255)
    upload_datetime = models.DateTimeField()
    uploader_user_id = models.IntegerField()
    deleted_flag = models.BooleanField()
    deleted_datetime = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'resources'

class RoleAssignmentHistory(models.Model):
    assignment_id = models.IntegerField(primary_key=True)
    user = models.OneToOneField('Users', models.DO_NOTHING)
    role = models.OneToOneField('Roles', models.DO_NOTHING)
    valid_from = models.DateTimeField(unique=True)
    valid_to = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'role_assignment_history'

class Roles(models.Model):
    role_id = models.IntegerField(primary_key=True)
    role_name = models.CharField(unique=True, max_length=255)

    class Meta:
        managed = False
        db_table = 'roles'