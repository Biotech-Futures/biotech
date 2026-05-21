"""Auth backend that caches User instances in Redis to avoid hitting the DB
on every authenticated request.

`django.contrib.auth.middleware.AuthenticationMiddleware` resolves
`request.user` lazily by calling `backend.get_user(user_id)`. The default
`ModelBackend` does `User.objects.select_related(...).get(pk=user_id)` —
one DB query per authenticated request. Under load with hundreds of
concurrent users browsing, this is the single hottest read on the box.

Caching the User object for a short TTL takes that query off the hot path
without changing any call-site code. Invalidation happens on User.save()
via the post_save signal in apps/users/signals.py.
"""
from __future__ import annotations

from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache


USER_CACHE_TTL_SECONDS = 60
USER_CACHE_KEY_PREFIX = "auth_user"


def user_cache_key(user_id) -> str:
    return f"{USER_CACHE_KEY_PREFIX}:{user_id}"


class CachedModelBackend(ModelBackend):
    """ModelBackend that caches get_user() results in Redis.

    Authenticate path is unchanged — only the per-request user resolution
    is cached. TTL is short (60s) so a suspended/deactivated user can't
    keep using the app for more than a minute past their account change.
    The post_save signal also clears the cache immediately on writes.
    """

    def get_user(self, user_id):
        key = user_cache_key(user_id)
        user = cache.get(key)
        if user is not None:
            return user
        user = super().get_user(user_id)
        if user is not None:
            cache.set(key, user, USER_CACHE_TTL_SECONDS)
        return user
