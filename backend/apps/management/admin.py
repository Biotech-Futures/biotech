from django.contrib import admin

from .models import GradingSettings, MarksRelease


@admin.register(MarksRelease)
class MarksReleaseAdmin(admin.ModelAdmin):
    list_display = ("id", "released_at", "released_by")
    raw_id_fields = ("released_by",)


@admin.register(GradingSettings)
class GradingSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "director_1_name", "director_2_name")
