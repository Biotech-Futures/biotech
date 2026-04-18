from django.contrib import admin

from .models import MatchRecommendation, MatchRun


class MatchRecommendationInline(admin.TabularInline):
    model = MatchRecommendation
    extra = 0


@admin.register(MatchRun)
class MatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "run_type", "initiated_by_user", "track", "created_at")
    list_filter = ("run_type", "track", "created_at")
    search_fields = ("initiated_by_user__email",)
    inlines = [MatchRecommendationInline]


@admin.register(MatchRecommendation)
class MatchRecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "match_run", "group", "mentor_user", "score", "accepted")
    list_filter = ("accepted",)
    search_fields = ("mentor_user__email", "group__group_name")

