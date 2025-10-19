# RESOURCES & ROLES MODELS

from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class ResourceRoles(models.Model):
    resource = models.ForeignKey('Resources', on_delete=models.CASCADE, related_name='resourceroles') # changed to regular FK, as one to one would force limit a resource to one role only
    role = models.ForeignKey('Roles', on_delete=models.CASCADE)

    class Meta:
        db_table = 'resource_roles'
        indexes = [
            models.Index(fields=['role'])
        ]
        constraints = [
            models.UniqueConstraint(fields=['resource', 'role'], name='pk_resource_role')
        ]
        verbose_name = "Resource Role"
        verbose_name_plural = "Resource Roles"

    def __str__(self):
        return f"{self.resource} -> {self.role}"

class ResourceType(models.Model):
    type_name = models.CharField(max_length=50, unique=True)
    type_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'resource_types'
        verbose_name = "Resource Type"
        verbose_name_plural = "Resource Types"

    def __str__(self):
        return self.type_name

class Resources(models.Model):
    resource_name = models.CharField(max_length=255)
    resource_description = models.CharField(max_length=255)
    resource_type = models.ForeignKey('ResourceType', on_delete=models.PROTECT, related_name='resources', null=True, blank=True)
    
    # File storage field for uploading resources to Azure blob storage
    resource_file = models.FileField(
        upload_to='resources/%Y/%m/%d/',
        null=False,
        blank=False,
        help_text="Upload a file for this resource (stored in Azure blob storage) - REQUIRED"
    )
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    content_type = models.CharField(max_length=100, null=True, blank=True, help_text="MIME type of the file")
    
    upload_datetime = models.DateTimeField(default=timezone.now)
    uploader_user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'resources'
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        indexes = [
            models.Index(fields=['uploader_user_id']),
        ]
        constraints = [
            # Ensure deleted_flag is always either True or False
            models.CheckConstraint(
                condition=Q(deleted_datetime__isnull=True) | Q(deleted_flag=True),
                name='deleted_flag_true_if_deleted_datetime'
            ),
            # Ensure resource names are unique if provided
            models.CheckConstraint(
                condition=Q(deleted_datetime__gte=F('upload_datetime')) | Q(deleted_datetime__isnull=True),
                name='deleted_after_upload'
            ),
            # Ensure resource_description is not empty
            models.CheckConstraint(
                condition=~Q(resource_description=''),
                name='resource_description_not_empty'
            ),
            # Ensure upload_datetime is not in the future (temporarily disabled due to timezone issues)
            # models.CheckConstraint(
            #     condition=Q(upload_datetime__lte=models.functions.Now()),
            #     name='resource_upload_not_future'
            # ),
        ]

    def __str__(self):
        return self.resource_name or f"Resource {self.id}"

class RoleAssignmentHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True) # Set null to allow history to persist if user is deleted
    role = models.ForeignKey('Roles', on_delete=models.SET_NULL, null=True) # Set null to allow history to persist if role is deleted
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'role_assignment_history'
        verbose_name = "Role Assignment History"
        verbose_name_plural = "Role Assignment Histories"
        constraints = [
            models.UniqueConstraint(fields=['user', 'role', 'valid_from'], name='unique_user_role_start'),
            # Ensure valid_to is after valid_from if valid_to is set
            models.CheckConstraint(
                condition=Q(valid_to__gte=F('valid_from')),
                name='valid_to_after_valid_from'
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['role']),
        ]
    def __str__(self):
        return f"{self.user} as {self.role} from {self.valid_from} to {self.valid_to or 'present'}"

class Roles(models.Model):
    role_name = models.CharField(unique=True, max_length=255)

    class Meta:
        db_table = 'roles'
        verbose_name = "Role"
        verbose_name_plural = "Roles"

        constraints = [
            # Ensure role names are unique and not empty
            models.CheckConstraint(
                condition=~Q(role_name=''),
                name='role_name_not_empty'
            )
        ]

    def __str__(self):
        return self.role_name