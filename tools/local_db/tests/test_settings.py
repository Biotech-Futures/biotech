import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_DIR.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"


class DockerSettingsIsolationTests(unittest.TestCase):
    def test_malformed_backend_env_is_not_loaded(self):
        """The tool must use Compose env/defaults even beside a hostile .env."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_backend = Path(temporary_directory) / "backend"
            temporary_config = temporary_backend / "config"
            temporary_config.mkdir(parents=True)
            for filename in ("__init__.py", "settings.py", "settings_local.py"):
                shutil.copy2(
                    BACKEND_DIR / "config" / filename,
                    temporary_config / filename,
                )

            (temporary_backend / ".env").write_text(
                "\n".join(
                    (
                        "EMAIL_PORT=not-an-integer",
                        "DB_CONN_MAX_AGE=also-not-an-integer",
                        "REDIS_URL=redis://personal-host.invalid:6379/0",
                        "DB_NAME=personal_database",
                        "DB_HOST=personal-host.invalid",
                    )
                ),
                encoding="utf-8",
            )

            script = textwrap.dedent(
                f"""
                import json
                from decouple import AutoConfig

                personal_config = AutoConfig(search_path={str(temporary_backend)!r})
                try:
                    personal_config("EMAIL_PORT", cast=int)
                except ValueError:
                    pass
                else:
                    raise AssertionError("the test .env was not malformed")

                import django_settings as settings

                database = settings.DATABASES["default"]
                print(json.dumps({{
                    "database": {{
                        "engine": database["ENGINE"],
                        "name": database["NAME"],
                        "user": database["USER"],
                        "password_matches_compose": database["PASSWORD"] == "biotech",
                        "host": database["HOST"],
                        "port": database["PORT"],
                        "options": database["OPTIONS"],
                    }},
                    "email_port": settings.EMAIL_PORT,
                    "redis_url": settings.REDIS_URL,
                    "cache_backend": settings.CACHES["default"]["BACKEND"],
                }}))
                """
            )
            python_path = os.pathsep.join(
                (str(TOOL_DIR), str(temporary_backend), str(BACKEND_DIR))
            )
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": python_path,
                "PYTHONIOENCODING": "utf-8",
                "DEBUG": "true",
                "DB_NAME": "biotech_dev",
                "DB_USER": "biotech",
                "DB_PASSWORD": "biotech",
                "DB_HOST": "postgres",
                "DB_PORT": "5432",
                "DB_SSLMODE": "disable",
                "LOCAL_DB_TOOL_GUARD": "BIOTECH_LOCAL_SYNTHETIC_DATA_ONLY",
                "LOCAL_DB_EXPECTED_NAME": "biotech_dev",
                "LOCAL_DB_EXPECTED_HOST": "postgres",
            }
            completed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["database"],
            {
                "engine": "django.db.backends.postgresql",
                "name": "biotech_dev",
                "user": "biotech",
                "password_matches_compose": True,
                "host": "postgres",
                "port": "5432",
                "options": {"sslmode": "disable", "connect_timeout": 5},
            },
        )
        self.assertEqual(payload["email_port"], 2525)
        self.assertEqual(payload["redis_url"], "")
        self.assertEqual(
            payload["cache_backend"],
            "django.core.cache.backends.locmem.LocMemCache",
        )


if __name__ == "__main__":
    unittest.main()
