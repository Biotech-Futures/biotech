#!/usr/bin/env python3
"""One-command interface for the Docker-contained local dataset generator."""

from __future__ import annotations

import argparse
import json
import sys
import unittest
from dataclasses import fields
from pathlib import Path

from dataset import DATASET_SCENARIOS, EMAIL_TYPES, EMAIL_STATUSES, DatasetConfig
from operations import (
    bootstrap_dataset,
    database_write_lock,
    get_dataset_status,
    setup_django,
)


TOOL_DIR = Path(__file__).resolve().parent


def _non_negative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = DatasetConfig()
    descriptions = {
        "admins": "admin users",
        "supervisors": "supervisor users",
        "mentors": "mentor users",
        "students": "student users",
        "groups": "programme groups",
        "messages": "group chat messages",
        "login_events": "successful-login audit events",
        "tasks": "group/individual tasks",
        "resources": "resource metadata rows",
        "resource_accesses": "resource access/click events",
        "announcements": "announcements",
        "deliveries": "announcement delivery summaries",
        "events": "programme events",
        "rsvps": "event RSVP rows",
    }
    for name, description in descriptions.items():
        parser.add_argument(
            f"--{name.replace('_', '-')}",
            type=_non_negative,
            default=getattr(defaults, name),
            help=f"number of {description} (default: {getattr(defaults, name)})",
        )
    parser.add_argument(
        "--scenario",
        choices=DATASET_SCENARIOS,
        default=defaults.scenario,
        help=(
            "deterministic distribution profile "
            f"(default: {defaults.scenario})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=defaults.seed,
        help=f"deterministic random seed (default: {defaults.seed})",
    )
    parser.add_argument(
        "--as-of",
        default=defaults.as_of,
        help=f"fixed ISO-8601 dataset clock (default: {defaults.as_of})",
    )
    parser.add_argument('--email-mode', choices=('coverage', 'custom'), default=defaults.email_mode,
                        help='coverage preserves preset deliveries; custom uses the email options below')
    parser.add_argument('--email-batches', type=_non_negative, default=defaults.email_batches,
                        help='exact total email batches in custom mode (no automatic extra batches)')
    parser.add_argument('--email-type', choices=('mixed', *EMAIL_TYPES), default=defaults.email_type)
    parser.add_argument('--email-status', choices=('mixed', *EMAIL_STATUSES), default=defaults.email_status)
    parser.add_argument('--email-recipients', type=_non_negative, default=defaults.email_recipients,
                        help='active synthetic recipients per custom batch')
    parser.add_argument('--email-start', default=defaults.email_start, help='first batch UTC time; defaults to dataset clock minus 23 hours')
    parser.add_argument('--email-end', default=defaults.email_end, help='last batch UTC time; defaults to dataset clock minus 5 minutes')


def _config_from_args(args) -> DatasetConfig:
    values = {field.name: getattr(args, field.name) for field in fields(DatasetConfig)}
    try:
        return DatasetConfig(**values).validate()
    except ValueError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc


def _json(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _safe_target():
    from safety import assert_safe_database

    target = assert_safe_database()
    print(f"Validated local target: {target.display()}")
    return target


def _run_bootstrap(args) -> int:
    config = _config_from_args(args)
    if args.dry_run:
        setup_django()
        _safe_target()
        _json({"operation": "bootstrap", "clear_database": True, "config": config.to_manifest()})
        return 0

    _, result = bootstrap_dataset(
        config,
        migration_verbosity=1,
        progress=print,
    )
    _json(result)
    return 0


def _run_generate(args) -> int:
    config = _config_from_args(args)
    setup_django()
    _safe_target()
    if args.dry_run:
        _json(
            {
                "operation": "generate",
                "replace": args.replace,
                "config": config.to_manifest(),
            }
        )
        return 0

    from django.db import transaction

    from generator import generate_dataset
    from safety import assert_migrations_current
    from verification import verify_dataset

    with database_write_lock():
        assert_migrations_current()
        with transaction.atomic():
            generate_dataset(
                config,
                replace=args.replace,
                allow_existing_data=args.allow_existing_data,
            )
            result = verify_dataset(check_migrations=False)
    print("Dataset generated and verified.")
    _json(result)
    return 0


def _run_verify(_args) -> int:
    setup_django()
    _safe_target()
    from verification import verify_dataset

    result = verify_dataset()
    print("Dataset verification passed.")
    _json(result)
    return 0


def _run_status(_args) -> int:
    payload = get_dataset_status()
    print(f"Validated local target: {payload['target']}")
    _json(payload)
    return 0


def _run_reset(args) -> int:
    if not args.yes:
        raise SystemExit(
            "reset deletes generated rows; repeat with --yes after checking the displayed target"
        )
    setup_django()
    _safe_target()
    from django.db import transaction

    from generator import wipe_dataset
    from safety import assert_migrations_current
    from verification import snapshot_counts

    with database_write_lock():
        assert_migrations_current()
        with transaction.atomic():
            removed = wipe_dataset()
            remaining = snapshot_counts()
            if any(remaining.values()):
                raise RuntimeError(
                    f"reset left generator-owned rows behind; rolling back: {remaining}"
                )
    print("Removed only Team 4 synthetic rows. Shared catalogues were retained.")
    _json({"removed_base_counts": removed})
    return 0


def _run_tests(_args) -> int:
    suite = unittest.defaultTestLoader.discover(str(TOOL_DIR / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic Team 4 development data in the project's local "
            "Docker PostgreSQL database."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="clear the local demo database, rebuild migrations, generate, and verify",
    )
    _add_dataset_arguments(bootstrap)
    bootstrap.add_argument("--dry-run", action="store_true", help="show the target/config only")
    bootstrap.set_defaults(handler=_run_bootstrap)

    generate = subparsers.add_parser(
        "generate", help="generate without running migrations"
    )
    _add_dataset_arguments(generate)
    generate.add_argument(
        "--replace",
        action="store_true",
        help="remove a prior Team 4 synthetic dataset before generating",
    )
    generate.add_argument("--dry-run", action="store_true", help="show the target/config only")
    generate.add_argument(
        "--allow-existing-data",
        action="store_true",
        help="preserve and combine unrelated local business rows (aggregate totals will differ)",
    )
    generate.set_defaults(handler=_run_generate)

    verify = subparsers.add_parser("verify", help="verify counts, relations, migrations, and fingerprint")
    verify.set_defaults(handler=_run_verify)

    status = subparsers.add_parser("status", help="show the redacted target and generated row inventory")
    status.set_defaults(handler=_run_status)

    reset = subparsers.add_parser("reset", help="delete only rows owned by this generator")
    reset.add_argument("--yes", action="store_true", help="confirm deletion of generated rows")
    reset.set_defaults(handler=_run_reset)

    tests = subparsers.add_parser("test", help="run generator unit tests without writing data")
    tests.set_defaults(handler=_run_tests)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        print("Interrupted; the active database transaction was rolled back.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
