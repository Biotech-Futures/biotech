from django.contrib import admin
from .models import Messages, MessageAttachments, MessageResource

admin.site.register(Messages)
admin.site.register(MessageAttachments)
admin.site.register(MessageResource)
