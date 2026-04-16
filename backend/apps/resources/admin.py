from django.contrib import admin
from .models import Resources, Roles, ResourceAudience, RoleAssignmentHistory, ResourceType

# Register your models here.
admin.site.register(ResourceType)
admin.site.register(Resources)
admin.site.register(Roles)
admin.site.register(ResourceAudience)
admin.site.register(RoleAssignmentHistory)
