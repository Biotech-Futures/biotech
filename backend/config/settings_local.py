import os

from .settings import *

# Dev-only secret
SECRET_KEY = "dev-only-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Use local Postgres for dev so schema behavior matches production/migrations.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT"),
        "CONN_MAX_AGE": 0,
    }
}

# Use local file storage instead of Azure Blob
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# Keep email local and visible in terminal
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Dev cookies
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Local frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Dev callback
MAGIC_LINK_REDIRECT_URL = "http://localhost:5173/#/auth/callback"

# Channels dev config
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
