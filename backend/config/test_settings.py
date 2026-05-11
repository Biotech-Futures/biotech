from .settings import *

# Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# CI has no Azure credentials; route managed-file uploads to the local backend.
USE_AZURE_BLOB_STORAGE = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

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