"""ASGI entrypoint wiring HTTP and WebSocket protocols."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "btf_backend.settings")

import django  # noqa: E402

django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

from core.websockets import JWTAuthMiddlewareStack  # noqa: E402
from .routing import websocket_urlpatterns  # noqa: E402

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
