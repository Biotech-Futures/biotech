from django.contrib import admin

from .models import (
    Deadline,
    GroupExtension,
    Submission,
    SubmissionInstruction,
    SubmissionQuestion,
)


@admin.register(SubmissionInstruction)
class SubmissionInstructionAdmin(admin.ModelAdmin):
    list_display = ("section", "updated_at")
    # Sections are seeded and fixed; only their wording is editable.
    readonly_fields = ("section", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SubmissionQuestion)
class SubmissionQuestionAdmin(admin.ModelAdmin):
    list_display = ("order", "key", "prompt", "is_required", "is_active")
    list_editable = ("order", "is_required", "is_active")
    list_display_links = ("key",)

    def get_readonly_fields(self, request, obj=None):
        # Answers are stored under the key, so it cannot change once created.
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
    list_display = (
        "group", "is_submitted", "submitted_at", "poster_flags", "is_late", "updated_at",
    )
    list_filter = ("is_late",)
    search_fields = ("group__group_name",)
    readonly_fields = ("created_at", "updated_at")

    list_select_related = ("group",)

    @admin.display(boolean=True, description="Submitted")
    def is_submitted(self, obj):
        return obj.is_submitted

    @admin.display(description="Poster format")
    def poster_flags(self, obj):
        """Format check summary, preferring the submitted poster over a draft one."""
        flag = obj.submitted_poster_checks or obj.poster_checks
        if not flag:
            return "—"
        if flag.get("unreadable"):
            return "Could not read"
        warnings = flag.get("warnings") or []
        if not flag.get("has_text", True):
            return "No text to check"
        return "OK" if not warnings else f"{len(warnings)} warning(s)"
