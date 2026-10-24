"""Settings for the PostgreSQL job in CI.

Deliberately NOT settings_test: that module disables migrations, which is the
one thing this job exists to run. And deliberately not settings_local either,
which expects a developer's .env.

What it is: settings_local's shape — DEBUG on so the fail-loud URL guards in
settings.py stay quiet, local file storage, email sent inline — pointed at the
database the workflow's service container provides through DB_* environment
variables, which settings.py already reads.
"""

import os

# settings.py raises ImproperlyConfigured for FRONTEND_BASE_URL and friends
# unless DEBUG is on or they are set. Has to happen before the import below,
# or settings.py crashes before this module's own DEBUG line can run.
os.environ.setdefault("DEBUG", "true")

from .settings import *  # noqa: F401,F403

SECRET_KEY = "ci-only-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# No Azure credentials in CI, and nothing here should reach the network.
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_ROOT = BASE_DIR / "ci-media"  # noqa: F405
MEDIA_URL = "/media/"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Inline, so a test can never leave a pool thread running past the assertion
# that was waiting on it.
AUTH_EMAIL_DISPATCH_SYNC = True

# The service container speaks plain TCP with no certificate.
DATABASES["default"]["OPTIONS"] = {}  # noqa: F405
