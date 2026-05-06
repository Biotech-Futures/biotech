from .settings import *

# Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

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