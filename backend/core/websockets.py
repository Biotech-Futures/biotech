"""Utilities for authenticating WebSocket connections using JWT tokens."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs

from channels.sessions import CookieMiddleware, SessionMiddleware
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthMiddleware(BaseMiddleware):
    """Attach a JWT-authenticated user to the connection scope."""

    def __init__(self, inner):
        super().__init__(inner)
        self._jwt_auth = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        close_old_connections()

        # If the user is already authenticated (e.g. via session cookies) keep it.
        existing_user = scope.get("user")
        if getattr(existing_user, "is_authenticated", False):
            return await super().__call__(scope, receive, send)

        token = self._extract_token(scope)
        scope = dict(scope)
        scope["user"] = AnonymousUser()

        if token:
            try:
                scope["user"] = await self._authenticate(token)
            except Exception:
                # Invalid tokens fall back to AnonymousUser; the consumer will
                # decide whether to accept or close the connection.
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    def _extract_token(self, scope) -> Optional[str]:
        """Return the JWT token from headers or query parameters if present."""

        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }

        auth_header = headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()

        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string:
            params = parse_qs(query_string)
            for key in ("token", "access_token"):
                values = params.get(key)
                if values:
                    return values[0]

        return None

    @database_sync_to_async
    def _authenticate(self, token: str):
        validated = self._jwt_auth.get_validated_token(token)
        return self._jwt_auth.get_user(validated)


def JWTAuthMiddlewareStack(inner):
    """Session-aware middleware stack that also supports JWT query tokens."""

    return CookieMiddleware(SessionMiddleware(JWTAuthMiddleware(inner)))
