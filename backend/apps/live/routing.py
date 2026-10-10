from django.urls import re_path

from .consumers import LiveRoomConsumer

websocket_urlpatterns = [
    re_path(r"^ws/live/(?P<kind>[a-z_]+)/(?P<room_id>\d+)/$", LiveRoomConsumer.as_asgi()),
]
