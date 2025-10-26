"""Project-level ASGI routing configuration."""

from chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns

websocket_urlpatterns = [
    *chat_websocket_urlpatterns,
]
