from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # The route exposes a conversation id even though the current backing model is the
    # existing group chat table; that keeps the socket contract aligned with the frontend.
    re_path(r"^ws/chat/(?P<conversation_id>\d+)/$", ChatConsumer.as_asgi()),
]
