"""
The test settings on Postgres instead of in-memory SQLite, for CI's
``backend_tests_postgres`` job (``.github/workflows/main_biotechbe.yml``).

Production runs on Postgres, and SQLite lets through things Postgres refuses:
it ignores ``select_for_update``, doesn't enforce ``max_length``, and carries
on after a failed query where Postgres aborts the transaction.

Use::

    python manage.py test tests --settings=config.settings_test_postgres --noinput
"""

from .settings_test import *
from .settings_migrations import DATABASES  # Postgres from the environment only, never backend/.env
