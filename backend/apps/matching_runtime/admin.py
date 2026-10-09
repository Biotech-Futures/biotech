from django.contrib import admin

from .models import MatchRecommendation, MatchRun, MatchingConfig


class MatchRecommendationInline(admin.TabularInline):
    model = MatchRecommendation
    extra = 0


@admin.register(MatchRun)
class MatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "run_type", "initiated_by_user", "created_at")
    list_filter = ("run_type", "created_at")
    search_fields = ("initiated_by_user__email",)
    inlines = [MatchRecommendationInline]


@admin.register(MatchRecommendation)
class MatchRecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "match_run", "group", "mentor_user", "score", "accepted")
    list_filter = ("accepted",)
    search_fields = ("mentor_user__email", "group__group_name")


@admin.register(MatchingConfig)
class MatchingConfigAdmin(admin.ModelAdmin):
    """Django-admin fallback for the weights the API exposes.

    ``clean()`` on the model applies the same "must total 100" rule, so a save
    here is rejected exactly as the API would reject it.
    """

    list_display = (
        "id",
        "year_weight",
        "timezone_weight",
        "timezone_max_weight",
        "size_bonus_weight",
        "total_weight",
        "updated_by",
    )
    search_fields = ("updated_by__email",)
    readonly_fields = ("total_weight", "created_at", "updated_at")

