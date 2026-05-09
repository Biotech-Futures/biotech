"""
Canonical Django settings for automated tests (`manage.py test`).

Import base from ``settings_local`` so tests use SQLite media, lax cookies,
in-memory Channels — not production Azure/session defaults from ``settings``.

Use::

    DJANGO_SETTINGS_MODULE=config.settings_test
"""

from .settings_local import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

# Run Celery tasks inline so worker behaviour can be asserted without an
# external broker. Individual tests still mock ``.delay`` when they only care
# about dispatch.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
