from django.contrib import admin

from .models import PlanStage, PlanTask, PlanTaskCompletion


class ReadOnlyPlanAdmin(admin.ModelAdmin):
    """Inspect records without bypassing the feature's mutation services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlanStage)
class PlanStageAdmin(ReadOnlyPlanAdmin):
    list_display = ("name", "position", "deleted_at")


@admin.register(PlanTask)
class PlanTaskAdmin(ReadOnlyPlanAdmin):
    list_display = ("name", "stage", "audience_role", "completion_mode", "due_date")
    list_select_related = ("stage",)


@admin.register(PlanTaskCompletion)
class PlanTaskCompletionAdmin(ReadOnlyPlanAdmin):
    list_display = ("task", "group", "user", "completed", "updated_at")
    list_select_related = ("task", "group", "user")
