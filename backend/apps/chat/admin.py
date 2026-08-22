from django.contrib import admin
from .models import MessageScreening, Messages, MessageResource

admin.site.register(Messages)
admin.site.register(MessageResource)
admin.site.register(MessageScreening)
