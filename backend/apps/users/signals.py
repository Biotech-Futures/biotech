"""Signals for the users app. Currently: invalidate the CachedModelBackend
entry whenever a User row changes so admins/account-status changes are
reflected immediately instead of waiting for the 60s TTL."""
from __future__ import annotations

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .backends import user_cache_key
from .models import User


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def _invalidate_user_cache(sender, instance, **_kwargs):
    cache.delete(user_cache_key(instance.pk))
