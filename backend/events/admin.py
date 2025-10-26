from django.contrib import admin

from .models import Event, EventRegistration


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "date",
        "time",
        "location",
        "type",
        "capacity",
        "created_at",
    )
    list_filter = ("type", "date")
    search_fields = ("title", "description", "location")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "registered_at")
    search_fields = ("event__title", "user__email")
    list_select_related = ("event", "user")
