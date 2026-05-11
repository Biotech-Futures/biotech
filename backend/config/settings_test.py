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

# Run link-preview unfurls inline so tests can observe the DB row and the
# websocket broadcast immediately — no background thread spun up. The
# dispatcher reads this flag at call time (see apps/chat/tasks.dispatch_og).
LINK_PREVIEW_DISPATCH_SYNC = True

# `apps/common/storage.py` selects the Azure backend whenever this is truthy,
# which then tries to parse an AZURE_CONNECTION_STRING that CI doesn't set.
# Force-False here (rather than relying on settings_local.py) because the
# repo's .gitignore excludes settings_local.py, so CI's checked-in copy may
# not have the override.
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
