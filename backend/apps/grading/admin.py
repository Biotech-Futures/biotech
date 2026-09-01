from django.contrib import admin

from .models import (
    FinalistFlag,
    Grade,
    GradingJob,
    GradingSettings,
    MarksRelease,
    Rubric,
    RubricCriterion,
)


class RubricCriterionInline(admin.TabularInline):
    model = RubricCriterion
    extra = 0
    fields = ("order", "name", "max_mark", "description")
    ordering = ("order",)


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("id", "component", "year", "active")
    list_filter = ("year", "active", "component")
    inlines = [RubricCriterionInline]


@admin.register(RubricCriterion)
class RubricCriterionAdmin(admin.ModelAdmin):
    list_display = ("id", "rubric", "name", "max_mark", "order")
    list_filter = ("rubric__component", "rubric__year")
    search_fields = ("name",)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "criterion", "mark", "graded_by", "graded_at")
    list_filter = ("criterion__rubric__component",)
    raw_id_fields = ("submission", "criterion", "graded_by")
    date_hierarchy = "graded_at"


@admin.register(FinalistFlag)
class FinalistFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "flagged_by", "flagged_at", "notified")
    list_filter = ("notified",)
    raw_id_fields = ("group", "flagged_by")
    date_hierarchy = "flagged_at"


@admin.register(MarksRelease)
class MarksReleaseAdmin(admin.ModelAdmin):
    list_display = ("id", "released_at", "released_by")
    raw_id_fields = ("released_by",)


@admin.register(GradingSettings)
class GradingSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "director_1_name", "director_2_name")


@admin.register(GradingJob)
class GradingJobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "created_by", "created_at", "finished_at")
    list_filter = ("kind", "status")
    raw_id_fields = ("created_by",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "finished_at")
