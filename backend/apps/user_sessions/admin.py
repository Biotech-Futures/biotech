from django.contrib import admin
from .models import Alert, UserSession

# Register your models here.
admin.site.register(UserSession)
admin.site.register(Alert)
