from django.contrib import admin

from .models import EventRsvp, Events, EventTargetGroup, EventTargetRole, EventTargetTrack

# Register your models here.
admin.site.register(Events)
admin.site.register(EventRsvp)
admin.site.register(EventTargetGroup)
admin.site.register(EventTargetRole)
admin.site.register(EventTargetTrack)
