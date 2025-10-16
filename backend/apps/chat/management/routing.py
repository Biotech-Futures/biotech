from django.urls import re_path
from .consumers import GroupChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/groups/(?P<group_id>\d+)/$", GroupChatConsumer.as_asgi()),
]
