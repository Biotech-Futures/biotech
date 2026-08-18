from django.contrib import admin

from .models import Deadline, GroupExtension, Submission


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    list_display = ("closes_at", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(GroupExtension)
class GroupExtensionAdmin(admin.ModelAdmin):
    list_display = ("group", "extended_until", "granted_by", "granted_at")
    search_fields = ("group__group_name",)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("group", "is_submitted", "submitted_at", "is_late", "updated_at")
    list_filter = ("is_late",)
    search_fields = ("group__group_name",)
    readonly_fields = ("created_at", "updated_at")

    # Without this the changelist runs one extra query per row to fetch the
    # group name shown in list_display.
    list_select_related = ("group",)

    @admin.display(boolean=True, description="Submitted")
    def is_submitted(self, obj):
        return obj.is_submitted
