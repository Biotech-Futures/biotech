import http.client
import json
import os
import re
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from dataset import (
    DATASET_SCENARIOS,
    SCENARIO_ANALYTICS_COVERAGE,
    SCENARIO_UNIFORM,
    DatasetConfig,
    EMAIL_CONFIG_FIELDS,
)
from gui_server import (
    GenerationJobManager,
    JobAlreadyRunningError,
    LocalDbGuiHandler,
    LocalDbGuiServer,
    RequestValidationError,
    _payload_for_gui,
    _safe_error,
    build_gui_config,
    config_from_payload,
)
from operations import WRITE_LOCK_ID, database_write_lock


TOOL_DIR = Path(__file__).resolve().parents[1]


def valid_payload(**overrides):
    config = DatasetConfig().to_manifest()
    config["seed"] = str(config["seed"])
    config.update(overrides)
    return {"config": config, "confirm_replace": True}


def wait_for_terminal_state(manager, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = manager.snapshot()
        if snapshot["state"] in {"succeeded", "failed"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("generation job did not reach a terminal state")


class GuiConfigTests(unittest.TestCase):
    def test_defaults_and_fields_come_from_dataset_config(self):
        payload = build_gui_config("token")
        defaults = DatasetConfig().to_manifest()
        expected_defaults = {**defaults, "seed": str(defaults["seed"])}
        self.assertEqual(payload["defaults"], expected_defaults)
        self.assertEqual(payload["defaults"]["scenario"], SCENARIO_ANALYTICS_COVERAGE)
        self.assertEqual(
            {field["name"] for field in payload["count_fields"]},
            set(defaults) - {"scenario", "seed", "as_of", *EMAIL_CONFIG_FIELDS},
        )
        scenario_field = next(
            field
            for field in payload["distribution_fields"]
            if field["name"] == "scenario"
        )
        self.assertEqual(
            [option["value"] for option in scenario_field["options"]],
            list(DATASET_SCENARIOS),
        )
        self.assertTrue(
            all(option["description"] for option in scenario_field["options"])
        )
        resource_accesses = next(
            field
            for field in payload["count_fields"]
            if field["name"] == "resource_accesses"
        )
        self.assertIn("does not distinguish action type", resource_accesses["help"])
        self.assertNotIn("Open/download", resource_accesses["help"])

    def test_gui_payload_preserves_large_seed_as_a_decimal_string(self):
        seed = 123456789012345678901234567890123456789
        original = {
            "config": {"seed": seed},
            "manifest": {"config": {"seed": seed}},
        }
        converted = _payload_for_gui(original)
        self.assertEqual(converted["config"]["seed"], str(seed))
        self.assertEqual(converted["manifest"]["config"]["seed"], str(seed))
        self.assertIsInstance(original["config"]["seed"], int)

    def test_complete_payload_accepts_large_exact_decimal_seed(self):
        seed = "123456789012345678901234567890123456789"
        payload = valid_payload(seed=seed)
        config = config_from_payload(payload)
        self.assertEqual(config.seed, int(seed))
        self.assertEqual(config.to_manifest()["as_of"], payload['config']['as_of'])

    def test_timezone_offset_is_normalised_in_manifest(self):
        config = config_from_payload(
            valid_payload(as_of="2026-09-01T10:00:00+10:00")
        )
        self.assertEqual(config.to_manifest()["as_of"], "2026-09-01T00:00:00+00:00")

    def test_scenario_is_required_and_strictly_validated(self):
        config = config_from_payload(valid_payload(scenario=SCENARIO_UNIFORM))
        self.assertEqual(config.scenario, SCENARIO_UNIFORM)

        for value in ("", "unknown", True, 1, None, [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RequestValidationError, "scenario must be one of"):
                    config_from_payload(valid_payload(scenario=value))

        payload = valid_payload()
        del payload["config"]["scenario"]
        with self.assertRaisesRegex(RequestValidationError, "Missing configuration"):
            config_from_payload(payload)

    def test_unknown_missing_and_unconfirmed_requests_are_rejected(self):
        payload = valid_payload()
        payload["operation"] = "reset"
        with self.assertRaisesRegex(RequestValidationError, "Unknown request"):
            config_from_payload(payload)

        payload = valid_payload()
        del payload["config"]["messages"]
        with self.assertRaisesRegex(RequestValidationError, "Missing configuration"):
            config_from_payload(payload)

        payload = valid_payload()
        payload["confirm_replace"] = False
        with self.assertRaisesRegex(RequestValidationError, "confirmation"):
            config_from_payload(payload)

    def test_invalid_count_types_are_rejected(self):
        for value in (True, 1.5, "1", None, [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RequestValidationError, "whole number"):
                    config_from_payload(valid_payload(messages=value))

    def test_count_boundaries_and_relationship_rules_match_dataset_config(self):
        self.assertEqual(
            config_from_payload(valid_payload(messages=2_000_000)).messages,
            2_000_000,
        )
        with self.assertRaisesRegex(RequestValidationError, "safety limit"):
            config_from_payload(valid_payload(messages=2_000_001))
        with self.assertRaisesRegex(RequestValidationError, "cannot be negative"):
            config_from_payload(valid_payload(messages=-1))
        with self.assertRaisesRegex(RequestValidationError, "messages require"):
            config_from_payload(valid_payload(groups=0, messages=1))
        with self.assertRaisesRegex(RequestValidationError, "resource accesses require"):
            config_from_payload(
                valid_payload(resources=0, resource_accesses=1)
            )

    def test_invalid_seed_and_naive_time_are_rejected(self):
        for seed in (True, 1.2, "1; touch /tmp/no", "$(id)", "01", "-"):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(RequestValidationError, "decimal"):
                    config_from_payload(valid_payload(seed=seed))
        with self.assertRaisesRegex(RequestValidationError, "UTC offset"):
            config_from_payload(valid_payload(as_of="2026-09-01T00:00:00"))

    def test_seed_length_limit_applies_to_string_and_json_integer(self):
        for seed in ("9" * 201, int("9" * 201)):
            with self.subTest(seed_type=type(seed).__name__):
                with self.assertRaisesRegex(RequestValidationError, "at most 200"):
                    config_from_payload(valid_payload(seed=seed))

    def test_static_browser_contract_includes_scenario_and_complete_status_counts(self):
        html = (TOOL_DIR / "gui" / "index.html").read_text(encoding="utf-8")
        javascript = (TOOL_DIR / "gui" / "app.js").read_text(encoding="utf-8")
        styles = (TOOL_DIR / "gui" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="scenario"', html)
        self.assertIn('name="scenario" required', html)
        self.assertIn("--scenario ${config.scenario}", javascript)
        self.assertIn(
            'const CONFIG_STORAGE_KEY = "biotech.localDbGui.config.v7";',
            javascript,
        )
        self.assertIn(
            '"biotech.localDbGui.config.v4",',
            javascript,
        )
        self.assertIn(
            '"biotech.localDbGui.config.v3",',
            javascript,
        )
        self.assertIn(
            'const PRE_SCENARIO_CONFIG_STORAGE_KEY = "biotech.localDbGui.config.v2";',
            javascript,
        )
        self.assertIn(
            "if (storageKey === PRE_SCENARIO_CONFIG_STORAGE_KEY) delete migrated.scenario;",
            javascript,
        )
        self.assertIn("selected = { ...selected, ...migrated }", javascript)
        self.assertIn("select:focus", styles)
        self.assertIn("@media (max-width: 470px)", styles)
        for count_name in (
            "memberships",
            "messages",
            "login_events",
            "tasks",
            "resources",
            "resource_access_events",
            "announcements",
            "deliveries",
            "events",
            "rsvps",
        ):
            with self.subTest(count_name=count_name):
                self.assertIn(f'["{count_name}",', javascript)


class LauncherContractTests(unittest.TestCase):
    def test_macos_launcher_atomically_prepares_and_recreates_only_gui(self):
        launcher = (TOOL_DIR / "open_gui.command").read_text()
        self.assertTrue(launcher.startswith("#!/bin/sh\nset -eu\n"))

        required_fragments = (
            '"$gui_url/api/job"',
            '"state": "queued"',
            '"state": "running"',
            '"$gui_url/api/prepare-restart"',
            "confirm_restart",
            "compose ps --status running --quiet local-db-gui",
            "compose up --detach --wait --no-recreate postgres",
            "compose build local-db-gui",
            "prepare_gui_reload || prepare_result=$?",
            "compose up --detach --force-recreate --no-deps local-db-gui",
            '"$gui_url/api/health"',
            "compose logs --tail 50 local-db-gui",
            "compose stop local-db-gui",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, launcher)

        self.assertLess(
            launcher.index('"$gui_url/api/job"'),
            launcher.index("compose build local-db-gui"),
        )
        self.assertLess(
            launcher.index("compose build local-db-gui"),
            launcher.index("compose up --detach --wait --no-recreate postgres"),
        )
        self.assertLess(
            launcher.index("compose up --detach --wait --no-recreate postgres"),
            launcher.index("prepare_gui_reload || prepare_result=$?"),
        )
        self.assertLess(
            launcher.index("prepare_gui_reload || prepare_result=$?"),
            launcher.index("compose up --detach --force-recreate --no-deps local-db-gui"),
        )
        self.assertLess(
            launcher.index("compose up --detach --force-recreate --no-deps local-db-gui"),
            launcher.index('"$gui_url/api/health"'),
        )
        self.assertNotIn("restart postgres", launcher)
        self.assertNotIn("compose restart", launcher)
        self.assertNotIn("compose down", launcher)
        self.assertNotIn("down -v", launcher)
        self.assertNotIn("/Users/", launcher)

    def test_windows_launcher_is_path_independent_and_fail_closed(self):
        raw_launcher = (TOOL_DIR / "open_gui_windows.cmd").read_bytes()
        self.assertFalse(raw_launcher.startswith(b"\xef\xbb\xbf"))
        launcher = raw_launcher.decode("ascii")
        self.assertTrue(launcher.startswith("@echo off"))
        self.assertLess(max(len(line) for line in raw_launcher.splitlines()), 8191)

        required_fragments = (
            "@echo off",
            "setlocal EnableExtensions DisableDelayedExpansion",
            "%~dp0",
            "docker compose version",
            "docker context inspect",
            "if defined DOCKER_CONTEXT if defined DOCKER_HOST (",
            "$env:DOCKER_HOST",
            "'npipe:////./pipe/'",
            "[string]::IsNullOrWhiteSpace",
            ".StartsWith($prefix, $comparison)",
            "$dockerOs",
            "-cne 'linux'",
            '--project-directory "%REPO_ROOT%"',
            "%REPO_ROOT%\\docker-compose.dev.yml",
            "%SCRIPT_DIR%compose.generator.yml",
            "up --detach --wait --no-recreate postgres",
            "build local-db-gui",
            "up --detach --force-recreate --no-deps local-db-gui",
            'set "GUI_URL=http://127.0.0.1:8765"',
            "%GUI_URL%/api/job",
            "%GUI_URL%/api/prepare-restart",
            "'Origin' = $env:GUI_URL",
            "%GUI_URL%/api/health",
            "-NoLogo -NoProfile -NonInteractive",
            "Invoke-RestMethod",
            "-ErrorAction Stop",
            "$response.status -eq 'ok'",
            "exit 0",
            "exit 1",
            'start "" "%GUI_URL%"',
            "goto gui_failed",
            "stop local-db-gui",
            "exit /b 0",
            "exit /b 1",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, launcher)

        self.assertNotRegex(launcher.lower(), r"(?m)^\s*for /f\s")
        self.assertIn('for %%I in ("%SCRIPT_DIR%..\\..")', launcher)

        nonempty_lines = [line.strip() for line in launcher.splitlines() if line.strip()]

        def assert_next_line(command, expected):
            index = nonempty_lines.index(command)
            self.assertEqual(nonempty_lines[index + 1], expected)

        assert_next_line("where docker >nul 2>&1", "if errorlevel 1 (")
        assert_next_line("docker compose version >nul 2>&1", "if errorlevel 1 (")
        assert_next_line("where powershell.exe >nul 2>&1", "if errorlevel 1 (")
        assert_next_line("docker info >nul 2>&1", "if errorlevel 1 (")
        assert_next_line(
            'docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" up --detach --force-recreate --no-deps local-db-gui',
            "if errorlevel 1 (",
        )
        powershell_lines = [
            line for line in nonempty_lines if line.startswith("powershell.exe ")
        ]
        self.assertEqual(len(powershell_lines), 5)
        endpoint_check = next(
            line for line in powershell_lines if "docker context inspect" in line
        )
        os_check = next(line for line in powershell_lines if "$dockerOs" in line)
        job_check = next(line for line in powershell_lines if "/api/job" in line)
        prepare_check = next(
            line for line in powershell_lines if "/api/prepare-restart" in line
        )
        health_check = next(
            line for line in powershell_lines if "/api/health" in line
        )
        assert_next_line(endpoint_check, "if errorlevel 2 (")
        assert_next_line(os_check, "if errorlevel 1 (")
        assert_next_line(job_check, "if errorlevel 2 (")
        assert_next_line(prepare_check, "if errorlevel 3 (")
        assert_next_line(health_check, "if errorlevel 1 goto health_failed")
        assert_next_line('start "" "%GUI_URL%"', "if errorlevel 1 (")

        compose_lines = [
            line
            for line in nonempty_lines
            if line.startswith("docker compose ") and " compose version " not in line
        ]
        self.assertEqual(len(compose_lines), 5)
        for line in compose_lines:
            self.assertIn('--project-directory "%REPO_ROOT%"', line)
            self.assertIn('-f "%BASE_COMPOSE%"', line)
            self.assertIn('-f "%TOOL_COMPOSE%"', line)
        logs_line = next(line for line in compose_lines if " logs " in line)
        postgres_line = next(
            line for line in compose_lines if "--wait --no-recreate postgres" in line
        )
        build_line = next(line for line in compose_lines if " build local-db-gui" in line)
        gui_line = next(line for line in compose_lines if "--force-recreate" in line)
        stop_line = next(line for line in compose_lines if " stop " in line)
        self.assertLess(nonempty_lines.index(build_line), nonempty_lines.index(postgres_line))
        self.assertLess(nonempty_lines.index(postgres_line), nonempty_lines.index(prepare_check))
        self.assertLess(nonempty_lines.index(prepare_check), nonempty_lines.index(gui_line))
        self.assertLess(nonempty_lines.index(gui_line), nonempty_lines.index(health_check))
        assert_next_line(gui_line, "if errorlevel 1 (")
        self.assertLess(nonempty_lines.index(logs_line), nonempty_lines.index(stop_line))
        assert_next_line(stop_line, "goto failure")

        labels = {
            match.group(1).lower()
            for match in re.finditer(r"(?m)^:([a-z0-9_]+)\s*$", launcher, re.I)
        }
        targets = {
            match.group(1).lower()
            for match in re.finditer(r"(?im)\bgoto\s+([a-z0-9_]+)", launcher)
        }
        self.assertTrue(targets)
        self.assertEqual(targets - labels, set())

        self.assertNotIn("tcp://", launcher)
        self.assertNotIn("ssh://", launcher)
        self.assertNotIn("unix://", launcher)
        self.assertNotIn("/Users/", launcher)
        self.assertNotIn("%*", launcher)
        self.assertNotIn("%DOCKER_CONTEXT%", launcher)
        self.assertNotIn("%DOCKER_HOST%", launcher)
        self.assertNotIn("DOCKER_ENDPOINT", launcher)
        self.assertNotIn("DOCKER_OS", launcher)
        self.assertNotIn("EnableDelayedExpansion", launcher)
        self.assertNotIn("cmd /c", launcher.lower())
        self.assertNotIn("restart postgres", launcher.lower())
        self.assertNotIn(" restart local-db-gui", launcher.lower())
        self.assertNotRegex(launcher.lower(), r"\b(?:python|node|npm|pip)\b")
        self.assertNotRegex(launcher.lower(), r"\bdocker compose\b.*\bdown\b")
        self.assertNotRegex(launcher.lower(), r"\bdocker compose\b.*(?:^|\s)-v(?:\s|$)")


class DatabaseWriteLockTests(unittest.TestCase):
    def _connection(self, acquired):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = (acquired,)
        connection = MagicMock()
        connection.cursor.return_value = cursor
        return connection, cursor

    def test_lock_is_acquired_and_released_even_when_work_fails(self):
        connection, cursor = self._connection(True)
        with patch("django.db.connection", connection):
            with self.assertRaisesRegex(RuntimeError, "fake work failed"):
                with database_write_lock():
                    raise RuntimeError("fake work failed")
        self.assertEqual(
            cursor.execute.call_args_list,
            [
                call("SELECT pg_try_advisory_lock(%s)", [WRITE_LOCK_ID]),
                call("SELECT pg_advisory_unlock(%s)", [WRITE_LOCK_ID]),
            ],
        )

    def test_lock_fails_fast_when_another_writer_is_active(self):
        connection, cursor = self._connection(False)
        with patch("django.db.connection", connection):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with database_write_lock():
                    self.fail("unavailable lock must not enter its body")
        cursor.execute.assert_called_once_with(
            "SELECT pg_try_advisory_lock(%s)", [WRITE_LOCK_ID]
        )


class GenerationJobManagerTests(unittest.TestCase):
    def test_only_one_job_can_run_at_a_time(self):
        started = threading.Event()
        release = threading.Event()

        def runner(config, **kwargs):
            started.set()
            release.wait(1)
            kwargs["progress"]("Finished fake work.")
            return "local target", {"config": config.to_manifest(), "counts": {}}

        manager = GenerationJobManager(runner=runner)
        manager.start(DatasetConfig())
        self.assertTrue(started.wait(1))
        with self.assertRaises(JobAlreadyRunningError):
            manager.start(DatasetConfig())
        with self.assertRaises(JobAlreadyRunningError):
            manager.prepare_for_restart()
        release.set()
        result = wait_for_terminal_state(manager)
        self.assertEqual(result["state"], "succeeded")
        self.assertIn("Finished fake work.", result["messages"])
        self.assertEqual(result["config"]["seed"], "3888")
        self.assertEqual(result["result"]["config"]["seed"], "3888")
        self.assertEqual(
            manager.prepare_for_restart(),
            {"state": "ready_for_restart"},
        )
        with self.assertRaisesRegex(
            JobAlreadyRunningError, "already being prepared"
        ):
            manager.prepare_for_restart()
        with self.assertRaisesRegex(JobAlreadyRunningError, "preparing to restart"):
            manager.start(DatasetConfig())

    def test_failure_is_redacted_and_releases_the_slot(self):
        calls = 0

        def runner(config, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("failure includes secret-value")
            return "local target", {"config": config.to_manifest(), "counts": {}}

        manager = GenerationJobManager(runner=runner)
        with patch.dict(os.environ, {"DB_PASSWORD": "secret-value"}):
            manager.start(DatasetConfig())
            failed = wait_for_terminal_state(manager)
        self.assertEqual(failed["state"], "failed")
        self.assertNotIn("secret-value", failed["error"])
        self.assertIn("[redacted]", failed["error"])

        manager.start(DatasetConfig())
        self.assertEqual(wait_for_terminal_state(manager)["state"], "succeeded")

    def test_safe_error_never_returns_password_values(self):
        with patch.dict(
            os.environ,
            {"DB_PASSWORD": "database-secret", "LOCAL_DB_LOGIN_PASSWORD": "login-secret"},
        ):
            message = _safe_error(RuntimeError("database-secret and login-secret"))
        self.assertEqual(message, "[redacted] and [redacted]")

    def test_thread_start_failure_returns_failed_state_and_releases_slot(self):
        def runner(config, **_kwargs):
            return "local target", {"config": config.to_manifest(), "counts": {}}

        manager = GenerationJobManager(runner=runner)
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("no thread")):
            failed = manager.start(DatasetConfig())
        self.assertEqual(failed["state"], "failed")
        self.assertIn("no thread", failed["error"])

        manager.start(DatasetConfig())
        self.assertEqual(wait_for_terminal_state(manager)["state"], "succeeded")


class GuiHttpTests(unittest.TestCase):
    def setUp(self):
        self.runner_calls = []

        def runner(config, **kwargs):
            self.runner_calls.append((config, kwargs))
            return "local target", {"config": config.to_manifest(), "counts": {}}

        class QuietHandler(LocalDbGuiHandler):
            def log_message(self, _format_string, *_args):
                return

        class QuietServer(LocalDbGuiServer):
            def handle_error(self, _request, _client_address):
                return

        self.handler = QuietHandler
        self.handler.csrf_token = "test-token"
        self.handler.manager = GenerationJobManager(runner=runner)
        self.server = QuietServer(("127.0.0.1", 0), self.handler)
        self.server.restart_preparation_timeout = 0.05
        self.port = self.server.server_address[1]
        self.handler.allowed_origins = {f"http://127.0.0.1:{self.port}"}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, method, path, *, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        if body is None or isinstance(body, (str, bytes)):
            encoded = body
        else:
            encoded = json.dumps(body)
        connection.request(method, path, body=encoded, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_headers, payload

    def test_static_assets_are_local_and_include_security_headers(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Local analytics dataset", body)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")

        traversal_status, _, _ = self.request("GET", "/../backend/.env")
        self.assertEqual(traversal_status, 404)

    def test_status_serializes_seed_closes_connections_and_redacts_failures(self):
        status_payload = {
            "target": "local target",
            "dataset_present": True,
            "counts": {"users": 1},
            "manifest": {"config": {"seed": 12345678901234567890}},
        }
        with patch("gui_server.get_dataset_status", return_value=status_payload), patch(
            "gui_server._close_django_connections"
        ) as close_connections:
            status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200, body)
        self.assertEqual(
            json.loads(body)["manifest"]["config"]["seed"],
            "12345678901234567890",
        )
        close_connections.assert_called_once_with()

        with patch.dict(os.environ, {"DB_PASSWORD": "database-secret"}), patch(
            "gui_server.get_dataset_status",
            side_effect=RuntimeError("failed with database-secret"),
        ), patch("gui_server._close_django_connections") as close_connections:
            status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 503, body)
        self.assertNotIn(b"database-secret", body)
        self.assertIn(b"[redacted]", body)
        close_connections.assert_called_once_with()

    def test_cross_origin_and_invalid_token_cannot_start_generation(self):
        common = {"Content-Type": "application/json"}
        status, _, _ = self.request(
            "POST",
            "/api/bootstrap",
            body=valid_payload(),
            headers={**common, "Origin": "https://example.invalid", "X-Local-DB-Token": "test-token"},
        )
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "POST",
            "/api/bootstrap",
            body=valid_payload(),
            headers={
                **common,
                "Origin": f"http://127.0.0.1:{self.port}",
                "X-Local-DB-Token": "wrong-token",
            },
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.runner_calls, [])

    def test_malformed_json_and_invalid_utf8_return_stable_400(self):
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Local-DB-Token": "test-token",
        }
        for body in (b"{", b"{\"config\":\"\xff\"}", b'{"config":{"seed":' + b"9" * 5000 + b"}}"):
            with self.subTest(body_prefix=body[:30]):
                status, _, response = self.request(
                    "POST", "/api/bootstrap", body=body, headers=headers
                )
                self.assertEqual(status, 400, response)
                self.assertEqual(json.loads(response)["error"], "Malformed JSON body.")
        self.assertEqual(self.runner_calls, [])

    def test_host_content_type_and_size_guards_reject_requests(self):
        origin = f"http://127.0.0.1:{self.port}"
        payload = valid_payload()
        status, _, _ = self.request(
            "POST",
            "/api/bootstrap",
            body=payload,
            headers={
                "Host": "example.invalid",
                "Content-Type": "application/json",
                "Origin": origin,
                "X-Local-DB-Token": "test-token",
            },
        )
        self.assertEqual(status, 421)

        status, _, _ = self.request(
            "POST",
            "/api/bootstrap",
            body=payload,
            headers={
                "Content-Type": "application/jsonp",
                "Origin": origin,
                "X-Local-DB-Token": "test-token",
            },
        )
        self.assertEqual(status, 415)

        status, _, _ = self.request(
            "POST",
            "/api/bootstrap",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(65 * 1024),
                "Origin": origin,
                "X-Local-DB-Token": "test-token",
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.runner_calls, [])

    def test_valid_same_origin_request_starts_fixed_bootstrap_job(self):
        status, _, body = self.request(
            "POST",
            "/api/bootstrap",
            body=valid_payload(
                messages=42,
                scenario=SCENARIO_UNIFORM,
                seed="-99",
            ),
            headers={
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.port}",
                "X-Local-DB-Token": "test-token",
            },
        )
        self.assertEqual(status, 202, body)
        job = json.loads(body)
        self.assertEqual(job["config"]["messages"], 42)
        self.assertEqual(job["config"]["scenario"], SCENARIO_UNIFORM)
        self.assertEqual(job["config"]["seed"], "-99")
        terminal = wait_for_terminal_state(self.handler.manager)
        self.assertEqual(terminal["state"], "succeeded")
        self.assertEqual(len(self.runner_calls), 1)
        generated_config, kwargs = self.runner_calls[0]
        self.assertEqual(generated_config.scenario, SCENARIO_UNIFORM)
        self.assertNotIn("allow_existing_data", kwargs)
        self.assertEqual(kwargs["migration_verbosity"], 0)

    def test_prepare_restart_atomically_disables_and_exits_if_abandoned(self):
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Local-DB-Token": "test-token",
        }
        status, _, body = self.request(
            "POST",
            "/api/prepare-restart",
            body={},
            headers=headers,
        )
        self.assertEqual(status, 400, body)
        with patch.object(
            self.server, "schedule_shutdown_after_restart_prepare"
        ) as schedule_shutdown:
            status, _, body = self.request(
                "POST",
                "/api/prepare-restart",
                body={"confirm_restart": True},
                headers=headers,
            )
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body), {"state": "ready_for_restart"})
        schedule_shutdown.assert_called_once_with()

        status, _, body = self.request(
            "POST",
            "/api/prepare-restart",
            body={"confirm_restart": True},
            headers=headers,
        )
        self.assertEqual(status, 409, body)
        self.assertIn("already being prepared", json.loads(body)["error"])

        status, _, body = self.request(
            "POST",
            "/api/bootstrap",
            body=valid_payload(),
            headers=headers,
        )
        self.assertEqual(status, 409, body)
        self.assertIn("preparing to restart", json.loads(body)["error"])

        self.server.schedule_shutdown_after_restart_prepare()
        self.thread.join(timeout=1)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.runner_calls, [])

    def test_prepare_restart_schedules_exit_even_if_response_disconnects(self):
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Local-DB-Token": "test-token",
        }
        with patch.object(
            self.server, "schedule_shutdown_after_restart_prepare"
        ) as schedule_shutdown, patch.object(
            self.handler, "_send_json", side_effect=BrokenPipeError
        ):
            with self.assertRaises(http.client.RemoteDisconnected):
                self.request(
                    "POST",
                    "/api/prepare-restart",
                    body={"confirm_restart": True},
                    headers=headers,
                )
        schedule_shutdown.assert_called_once_with()
        with self.assertRaisesRegex(JobAlreadyRunningError, "preparing to restart"):
            self.handler.manager.start(DatasetConfig())

    def test_second_http_request_returns_409_while_job_runs(self):
        started = threading.Event()
        release = threading.Event()

        def runner(config, **_kwargs):
            started.set()
            release.wait(1)
            return "local target", {"config": config.to_manifest(), "counts": {}}

        self.handler.manager = GenerationJobManager(runner=runner)
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Local-DB-Token": "test-token",
        }
        try:
            first, _, _ = self.request(
                "POST", "/api/bootstrap", body=valid_payload(), headers=headers
            )
            self.assertEqual(first, 202)
            self.assertTrue(started.wait(1))
            prepare, _, body = self.request(
                "POST",
                "/api/prepare-restart",
                body={"confirm_restart": True},
                headers=headers,
            )
            self.assertEqual(prepare, 409, body)
            second, _, body = self.request(
                "POST", "/api/bootstrap", body=valid_payload(), headers=headers
            )
            self.assertEqual(second, 409, body)
        finally:
            release.set()
        self.assertEqual(wait_for_terminal_state(self.handler.manager)["state"], "succeeded")


if __name__ == "__main__":
    unittest.main()
