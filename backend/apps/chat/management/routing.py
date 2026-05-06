from django.urls import re_path
from .consumers import GroupChatConsumer

websocket_urlpatterns = [
    # Keep the existing group-based route, but accept the newer conversation-style alias
    # so updated clients do not need a separate deployment cut-over.
    re_path(r"^ws/chat/(?P<conversation_id>\d+)/$", GroupChatConsumer.as_asgi()),
    re_path(r"^ws/chat/groups/(?P<group_id>\d+)/$", GroupChatConsumer.as_asgi()),
]
