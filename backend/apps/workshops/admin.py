from django.contrib import admin
from .models import Workshops, WorkshopAttendance

# Register your models here.
admin.site.register(Workshops)
admin.site.register(WorkshopAttendance)
