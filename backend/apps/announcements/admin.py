from django.contrib import admin
from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'audience', 'author', 'created_datetime', 'is_pinned', 'deleted_flag']
    list_filter = ['audience', 'is_pinned', 'deleted_flag', 'created_datetime']
    search_fields = ['title', 'summary', 'author__email', 'author__first_name', 'author__last_name']
    readonly_fields = ['created_datetime', 'updated_datetime', 'deleted_datetime']
    date_hierarchy = 'created_datetime'

    fieldsets = (
        ('Content', {
            'fields': ('title', 'summary', 'content')
        }),
        ('Targeting', {
            'fields': ('audience', 'is_pinned')
        }),
        ('Links', {
            'fields': ('external_link', 'internal_route'),
            'description': 'Choose either external link OR internal route, not both.'
        }),
        ('Metadata', {
            'fields': ('author', 'created_datetime', 'updated_datetime')
        }),
        ('Management', {
            'fields': ('deleted_flag', 'deleted_datetime'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Set author to current user if creating new announcement"""
        if not change:  # Creating new object
            obj.author = request.user
        super().save_model(request, obj, form, change)
