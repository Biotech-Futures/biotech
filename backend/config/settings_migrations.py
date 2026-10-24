"""
Settings for CI's migration check (the ``migrations`` job in
``.github/workflows/main_biotechbe.yml``).

``settings_test`` builds the test tables straight from the models, so the test
suite never loads a migration. This turns migrations back on against a real
Postgres, so CI catches two branches' migrations conflicting, a model change
with no migration, or a migration that won't apply, before production
migrates on deploy.

Use::

    python manage.py makemigrations --check --dry-run --settings=config.settings_migrations
    python manage.py migrate --noinput --settings=config.settings_migrations
"""

import os

from .settings_test import *

MIGRATION_MODULES = {}

# From the environment only, never backend/.env, so running this locally can't
# migrate whichever database .env points at. The defaults are CI's service
# container.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "postgres"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {"sslmode": "disable"},
    }
}
