from django.contrib import admin

from .models import Announcement, AnnouncementAudience


class AnnouncementAudienceInline(admin.TabularInline):
    model = AnnouncementAudience
    extra = 0


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author_user", "visibility_scope", "published_at", "archived_at")
    list_filter = ("visibility_scope", "published_at", "archived_at")
    search_fields = ("title", "body", "author_user__email")
    inlines = [AnnouncementAudienceInline]


@admin.register(AnnouncementAudience)
class AnnouncementAudienceAdmin(admin.ModelAdmin):
    list_display = ("id", "announcement", "role", "group")
    list_filter = ("role", "group")
