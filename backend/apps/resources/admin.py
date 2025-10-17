from django.contrib import admin
from .models import Resources, Roles, ResourceRoles, RoleAssignmentHistory, ResourceType

# Register your models here.
admin.site.register(ResourceType)
admin.site.register(Resources)
admin.site.register(Roles)
admin.site.register(ResourceRoles)
admin.site.register(RoleAssignmentHistory)
