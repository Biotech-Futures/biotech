"""Docker-only settings overlay for the disposable local dataset tool.

The application settings and model registry remain the source of truth.  This
overlay only pins side-effecting integrations to local implementations.
"""

import os

import decouple


os.environ.setdefault("DEBUG", "true")

# ``config.settings`` and ``config.settings_local`` import python-decouple's
# package-level ``config`` object. Replace it before either project module is
# imported so this tool process reads only explicit container environment
# variables and declared defaults, never a workstation's ``backend/.env``.
# ``RepositoryEmpty`` deliberately preserves normal ``os.environ`` precedence.
decouple.config = decouple.Config(decouple.RepositoryEmpty())

from config.settings_local import *  # noqa: E402,F403


DEBUG = True

# The compose overlay supplies explicit PostgreSQL values.  Re-apply them here
# so an ignored workstation .env can never redirect this container.
DATABASES["default"].update(  # noqa: F405
    {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
        "OPTIONS": {"sslmode": "disable", "connect_timeout": 5},
    }
)

# A generator must never contact SMTP, Azure Blob, Redis, or another process.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
AUTH_EMAIL_DISPATCH_SYNC = True
BULK_EMAIL_DISPATCH_SYNC = True
SCHEDULER_ENABLED = False
EMAIL_PRECHECK_ENABLED = False
EMAIL_CHECK_ON_EDIT = False
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
