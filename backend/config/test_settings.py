from .settings import *

# Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Keep the test profile hermetic even when CI or a developer shell has live
# Azure storage credentials in the environment.
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
BACKEND_URL = "http://localhost:8000"
FRONTEND_BASE_URL = "http://localhost:5173"
ADMIN_FRONTEND_BASE_URL = "https://mentoringadmin.biotechfutures.org"
MAGIC_LINK_REDIRECT_URL = f"{FRONTEND_BASE_URL}/#/auth/callback"
ADMIN_MAGIC_LINK_REDIRECT_URL = f"{ADMIN_FRONTEND_BASE_URL}/auth/callback"
PASSWORD_RESET_REDIRECT_URL = f"{FRONTEND_BASE_URL}/auth/reset-password"
ADMIN_PASSWORD_RESET_REDIRECT_URL = f"{ADMIN_FRONTEND_BASE_URL}/auth/reset-password"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@test.biotechfutures.org"

# Skip problematic app migrations entirely during tests
MIGRATION_MODULES = {
    'chat': None,
    'audit': None,
    'matching': None,
    'matching_runtime': None,
    'services': None,
    'tasks': None,
    'workshops': None,
    'certificates': None,
    'announcements': None,
}
