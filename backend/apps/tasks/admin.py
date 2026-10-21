from django.contrib import admin

from .models import RoleTask, RoleTaskCompletion, Task

admin.site.register(Task)
admin.site.register(RoleTask)
admin.site.register(RoleTaskCompletion)
