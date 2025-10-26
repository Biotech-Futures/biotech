from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "author", "created_at")
    list_filter = ("audience", "author")
    search_fields = ("title", "summary", "content", "author")
