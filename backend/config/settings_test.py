"""
Canonical Django settings for automated tests (`manage.py test`).

These run the tests on SQLite in memory, for quick local runs with no
database to start. CI runs them on Postgres instead, the database production
runs on (``config.settings_test_postgres``), which refuses things SQLite lets
through.

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

# CACHES is inherited from settings.py, which points at the shared Azure Redis
# whenever REDIS_URL is set — and throttle tests call cache.clear() in setUp,
# i.e. FLUSHDB against live infrastructure. Pin to per-process memory.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-locmem",
    }
}


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

# Same reason for auth mail: tests assert on msg.send(), which the pool would race.
AUTH_EMAIL_DISPATCH_SYNC = True

# The email jobs' tokens: tests set the ones they mean.
EMAIL_JOBS_TOKEN = ""
RSVP_REMINDER_TOKEN = ""
BULK_EMAIL_DISPATCH_SYNC = True
BULK_EMAIL_RETRY_SECONDS = 0
BULK_EMAIL_QUEUE_GAP_SECONDS = 0
# Every send tries the server: a test that wants a mailbox to stay down sets it.
MAIL_SERVER_DOWN_SECONDS = 0

# Dummy QuickEmailVerification keys, so no test can pick up a real one from the
# environment (its HTTP is mocked anyway), and its checks run inline.
QEV_API_KEY = "test-dummy-key"
QEV_PAID_API_KEY = "test-dummy-paid-key"
# Never let a developer's real key from .env make tests call (and pay for) Claude.
ANTHROPIC_API_KEY = ""
# Off whatever the environment says; the tests that need it turn it on.
EMAIL_PRECHECK_ENABLED = False
SCHEDULER_ENABLED = False
EMAIL_CHECK_ON_EDIT = False
EMAIL_VERIFICATION_DISPATCH_SYNC = True

# `apps/common/storage.py` selects the Azure backend whenever this is truthy,
# which then tries to parse an AZURE_CONNECTION_STRING that CI doesn't set.
# Force-False here (rather than relying on settings_local.py) because the
# repo's .gitignore excludes settings_local.py, so CI's checked-in copy may
# not have the override.
USE_AZURE_BLOB_STORAGE = False
# Same reason the flag above is forced: settings.py points STORAGES at Azure,
# and only replacing the dict keeps CI off a backend it has no credentials for.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Pinned on, so turning it off in a local .env cannot stop the suite testing it.
SUBMISSION_POSTER_CHECKS_ENABLED = True
