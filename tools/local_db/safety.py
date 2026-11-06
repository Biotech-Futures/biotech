"""Fail-closed checks for all database-writing generator commands."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


SAFETY_TOKEN = "BIOTECH_LOCAL_SYNTHETIC_DATA_ONLY"
ALLOWED_DATABASE_HOSTS = {"postgres"}


class UnsafeDatabaseError(RuntimeError):
    pass


def validate_reset_database_name(name: str) -> None:
    """Full resets are reserved for this workstation's disposable demo DBs."""
    if re.fullmatch(r"biotech_llm_demo_[a-z0-9_]+", name) is None:
        raise UnsafeDatabaseError(
            "full reset is only allowed for an isolated biotech_llm_demo_* database"
        )


@dataclass(frozen=True)
class DatabaseTarget:
    name: str
    host: str
    port: str
    vendor: str
    server_version: str

    def display(self) -> str:
        return (
            f"PostgreSQL {self.server_version} database {self.name!r} "
            f"via {self.host}:{self.port}"
        )


def validate_config_values(*, debug, engine: str, name: str, host: str) -> None:
    """Pure portion of the target guard, kept unit-testable without Django."""

    if os.environ.get("LOCAL_DB_TOOL_GUARD") != SAFETY_TOKEN:
        raise UnsafeDatabaseError(
            "LOCAL_DB_TOOL_GUARD is missing; run the tool through tools/local_db/run"
        )
    if debug is not True:
        raise UnsafeDatabaseError("refusing to run because Django DEBUG is not True")
    if engine != "django.db.backends.postgresql":
        raise UnsafeDatabaseError("the generator only supports PostgreSQL")

    expected_name = os.environ.get("LOCAL_DB_EXPECTED_NAME")
    expected_host = os.environ.get("LOCAL_DB_EXPECTED_HOST")
    if not expected_name or not expected_host:
        raise UnsafeDatabaseError("expected local database identity is not configured")
    if name != expected_name or host != expected_host:
        raise UnsafeDatabaseError(
            "configured database does not match the compose-local target "
            f"({expected_name!r} via {expected_host!r})"
        )
    if host not in ALLOWED_DATABASE_HOSTS:
        raise UnsafeDatabaseError(f"database host {host!r} is not a local compose service")
    lowered = name.casefold()
    if any(marker in lowered for marker in ("prod", "production", "staging", "azure")):
        raise UnsafeDatabaseError("database name looks shared or production-like")


def assert_safe_database() -> DatabaseTarget:
    from django.conf import settings
    from django.db import connection

    config = settings.DATABASES["default"]
    name = str(config.get("NAME", ""))
    host = str(config.get("HOST", ""))
    port = str(config.get("PORT", ""))
    validate_config_values(
        debug=settings.DEBUG,
        engine=str(config.get("ENGINE", "")),
        name=name,
        host=host,
    )

    connection.ensure_connection()
    if connection.vendor != "postgresql":
        raise UnsafeDatabaseError("connected database is not PostgreSQL")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_setting('server_version')")
        actual_name, server_version = cursor.fetchone()
    if actual_name != name:
        raise UnsafeDatabaseError(
            f"connected database {actual_name!r} does not match configured {name!r}"
        )
    major = str(server_version).split(".", 1)[0]
    if major != "16":
        raise UnsafeDatabaseError(
            f"expected PostgreSQL 16 to match docker-compose.dev.yml, got {server_version}"
        )
    return DatabaseTarget(
        name=name,
        host=host,
        port=port,
        vendor=connection.vendor,
        server_version=str(server_version),
    )


def assert_migrations_current() -> None:
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        preview = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in plan[:5])
        suffix = "..." if len(plan) > 5 else ""
        raise RuntimeError(
            f"database has {len(plan)} unapplied migration(s): {preview}{suffix}; "
            "run bootstrap instead of generate"
        )
