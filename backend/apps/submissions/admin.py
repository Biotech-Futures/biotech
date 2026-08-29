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
    # The three sections are fixed by the form's structure, so they are seeded
    # rather than created by hand and the section itself cannot be changed.
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
    list_display = (
        "group", "is_submitted", "submitted_at", "poster_flags", "is_late", "updated_at",
    )
    list_filter = ("is_late",)
    search_fields = ("group__group_name",)
    readonly_fields = ("created_at", "updated_at")

    # Without this the changelist runs one extra query per row to fetch the
    # group name shown in list_display.
    list_select_related = ("group",)

    @admin.display(boolean=True, description="Submitted")
    def is_submitted(self, obj):
        return obj.is_submitted

    @admin.display(description="Poster format")
    def poster_flags(self, obj):
        """What the format checks found, for someone scanning the list.

        Reads the submitted copy in preference to the working one so the column
        describes the poster on record rather than one uploaded during a
        revision that was never finished.
        """
        flag = obj.submitted_poster_checks or obj.poster_checks
        if not flag:
            return "—"
        if flag.get("unreadable"):
            return "Could not read"
        warnings = flag.get("warnings") or []
        if not flag.get("has_text", True):
            # Worth distinguishing: nothing was found wrong, but nothing could
            # be checked either, so this is "unknown" rather than "fine".
            return "No text to check"
        return "OK" if not warnings else f"{len(warnings)} warning(s)"
