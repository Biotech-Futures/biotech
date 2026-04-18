from django.contrib import admin

from .models import AdminAuthSession, AdminMatchRun, AdminOAuthAccount, AdminUser

admin.site.register(AdminUser)
admin.site.register(AdminOAuthAccount)
admin.site.register(AdminAuthSession)
admin.site.register(AdminMatchRun)
