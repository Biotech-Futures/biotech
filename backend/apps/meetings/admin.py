from django.contrib import admin

from .models import GroupMeeting, MeetingNote, MeetingSummary


@admin.register(GroupMeeting)
class GroupMeetingAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "organiser", "event", "created_at")
    list_select_related = ("group", "organiser", "event")
    search_fields = ("group__group_name", "event__event_name")
    raw_id_fields = ("event", "group", "organiser")
    date_hierarchy = "created_at"


@admin.register(MeetingNote)
class MeetingNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "revision", "updated_by", "updated_at")
    raw_id_fields = ("meeting", "updated_by")


@admin.register(MeetingSummary)
class MeetingSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "author", "published_at", "updated_at")
    list_filter = ("published_at",)
    raw_id_fields = ("meeting", "author")
