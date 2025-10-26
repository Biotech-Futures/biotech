from django.contrib import admin

from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "type",
        "role",
        "created_at",
        "download_count",
    )
    list_filter = ("type", "role")
    search_fields = ("title", "description")
