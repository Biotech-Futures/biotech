from django.contrib import admin
from .models import Messages, MessageAttachments

# Register your models here.
admin.site.register(Messages)
admin.site.register(MessageAttachments)
