from django.contrib import admin

from .models import Submission, SubmissionComponent


@admin.register(SubmissionComponent)
class SubmissionComponentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_optional", "accepts_file", "accepts_text", "accepts_link", "order")
    list_editable = ("order",)
    ordering = ("order", "id")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "component", "submitted_at", "submitted_by", "is_late")
    list_filter = ("component", "is_late")
    search_fields = ("group__group_name",)
    raw_id_fields = ("group", "submitted_by")
    date_hierarchy = "submitted_at"
