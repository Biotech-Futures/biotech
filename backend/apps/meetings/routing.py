from django.urls import re_path

from .consumers import MeetingNoteConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/meetings/(?P<meeting_id>\d+)/note/$",
        MeetingNoteConsumer.as_asgi(),
    ),
]
