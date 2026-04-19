from django.contrib import admin
from .models import AdminUser, Account, AdminSession, AdminMatchRun


@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "name", "email_verified", "created_at")
    search_fields = ("email", "name", "id")
    list_filter = ("email_verified",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "provider_id", "account_id", "user", "created_at")
    search_fields = ("provider_id", "account_id", "user__email")
    list_filter = ("provider_id",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(AdminSession)
class AdminSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "expires_at", "ip_address", "created_at")
    search_fields = ("user__email", "ip_address", "token")
    list_filter = ("expires_at",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(AdminMatchRun)
class AdminMatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "admin_user", "run_type", "created_at")
    search_fields = ("run_type", "admin_user__email")
    list_filter = ("run_type",)
    readonly_fields = ("created_at",)
    raw_id_fields = ("admin_user",)
    ordering = ("-created_at",)
