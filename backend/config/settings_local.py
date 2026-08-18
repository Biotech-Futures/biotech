import os

# settings.py fail-loud guards (FRONTEND_BASE_URL / ADMIN_FRONTEND_BASE_URL /
# BACKEND_URL) raise ImproperlyConfigured unless DEBUG or the env vars are set.
# Tests and fresh clones (and CI) have no .env, so force DEBUG on *before* the
# import below — otherwise settings.py crashes before this module's own
# `DEBUG = True` can run. setdefault leaves an explicit env override untouched.
os.environ.setdefault("DEBUG", "true")

from .settings import *

# Dev-only secret
SECRET_KEY = "dev-only-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Database configuration is safely inherited from settings.py mapping to .env,
# except for TLS: settings.py pins ``sslmode=require`` because Azure Postgres
# mandates it, but the local docker-compose.dev.yml container serves plain TCP
# and rejects the handshake with "server does not support SSL". Note that
# ``DB_SSLMODE`` in .env is *not* consulted by settings.py, so the override has
# to happen here rather than in the environment.
DATABASES["default"]["OPTIONS"]["sslmode"] = os.environ.get("DB_SSLMODE", "disable")

# Use local file storage instead of Azure Blob
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# Use proper email backend, falling back to what's mapped in settings.py (which uses SMTP)
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# conftest.py pins pytest to this module, and the backend above is real SMTP —
# send inline so a test can never leave a pool thread dialling the relay.
AUTH_EMAIL_DISPATCH_SYNC = True

# Dev cookies
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"

# Local frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Channels dev config
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
