from django.contrib import admin
from .models import Tasks, TaskAssignees, Milestone

# Register your models here.
admin.site.register(Tasks)
admin.site.register(TaskAssignees)
admin.site.register(Milestone)
