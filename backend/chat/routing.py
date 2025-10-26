"""WebSocket URL patterns for the chat application."""

from django.urls import path

from .consumers import GroupChatConsumer


websocket_urlpatterns = [
    path("ws/chat/groups/<str:group_id>/", GroupChatConsumer.as_asgi(), name="group-chat"),
]
