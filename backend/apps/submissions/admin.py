from django.contrib import admin

from .models import Deadline, GroupExtension, Submission, SubmissionQuestion


@admin.register(SubmissionQuestion)
class SubmissionQuestionAdmin(admin.ModelAdmin):
    list_display = ("order", "key", "prompt", "is_required", "is_active")
    list_editable = ("order", "is_required", "is_active")
    list_display_links = ("key",)

    def get_readonly_fields(self, request, obj=None):
        # The key is what stored answers are filed under, so it is fixed once
        # the question exists — changing it would orphan every answer already
        # written against it. New questions can still choose their own.
        return ("key",) if obj else ()


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
