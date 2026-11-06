"""Shared, Docker-contained operations used by the CLI and local GUI."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from dataset import DatasetConfig


TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

ProgressCallback = Callable[[str], None]
WRITE_LOCK_ID = 0x42494F5445434834  # ASCII-like stable key: "BIOTECH4"


def setup_django() -> None:
    """Load the real project model registry with the Docker-only settings overlay."""

    for path in (BACKEND_DIR, TOOL_DIR):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_settings")

    import django

    django.setup()


@contextmanager
def database_write_lock():
    """Fail fast when another generator process is writing to this database."""

    from django.db import connection

    acquired = False
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [WRITE_LOCK_ID])
        acquired = bool(cursor.fetchone()[0])
    if not acquired:
        raise RuntimeError(
            "another local dataset write is already running; wait for it to finish and retry"
        )
    try:
        yield
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [WRITE_LOCK_ID])
        except Exception:
            # Closing the PostgreSQL session also releases a session advisory lock.
            connection.close()


def bootstrap_dataset(
    config: DatasetConfig,
    *,
    migration_verbosity: int = 1,
    progress: ProgressCallback | None = None,
) -> tuple[str, dict]:
    """Clear, rebuild and verify the local demo DB in one PostgreSQL transaction."""

    setup_django()
    emit = progress or (lambda _message: None)

    from django.core.management import call_command
    from django.contrib.contenttypes.models import ContentType
    from django.db import connection, transaction

    from generator import generate_dataset
    from safety import assert_migrations_current, assert_safe_database, validate_reset_database_name
    from verification import verify_dataset

    config.validate()
    target = assert_safe_database()
    validate_reset_database_name(target.name)
    emit(f"Validated local target: {target.display()}")
    with database_write_lock():
        with transaction.atomic():
            emit("Clearing all data and application tables in the current local demo database...")
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '10s'")
                cursor.execute(
                    "SELECT nspname FROM pg_namespace "
                    "WHERE nspname <> 'information_schema' AND left(nspname, 3) <> 'pg_'"
                )
                schemas = [row[0] for row in cursor.fetchall()]
                for schema in schemas:
                    cursor.execute(f"DROP SCHEMA {connection.ops.quote_name(schema)} CASCADE")
                cursor.execute('CREATE SCHEMA "public"')
                cursor.execute('SET LOCAL search_path TO public')
            ContentType.objects.clear_cache()
            emit("Rebuilding tables and reference data from current project migrations...")
            call_command("migrate", interactive=False, verbosity=migration_verbosity)
            assert_migrations_current()
            emit("Writing the newly configured demo dataset...")
            generate_dataset(config, replace=False)
            result = verify_dataset(check_migrations=False)
    emit("Database rebuilt and dataset verified. Reload the demo website and sign in again.")
    return target.display(), result


def get_dataset_status() -> dict:
    """Return the same redacted dataset inventory used by the CLI and GUI."""

    setup_django()

    from safety import assert_migrations_current, assert_safe_database
    from verification import dataset_exists, load_manifest, snapshot_counts

    target = assert_safe_database()
    assert_migrations_current()
    payload = {
        "target": target.display(),
        "dataset_present": dataset_exists(),
        "counts": snapshot_counts(),
    }
    if payload["dataset_present"]:
        try:
            payload["manifest"] = load_manifest()
        except Exception as exc:  # status reports damage; verify remains fail-closed
            payload["manifest_error"] = str(exc)
    return payload
