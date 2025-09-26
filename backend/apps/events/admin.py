from django.contrib import admin
from .models import Events, EventInvite, EventTargetGroup, EventTargetRole, EventTargetTrack

# Register your models here.
admin.site.register(Events)
admin.site.register(EventInvite)
admin.site.register(EventTargetGroup)
admin.site.register(EventTargetRole)
admin.site.register(EventTargetTrack)
