#!/usr/bin/env python3
"""Loopback-only browser GUI for the Docker-contained dataset generator."""

from __future__ import annotations

import copy
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dataset import (
    DATASET_SCENARIOS,
    SCENARIO_ANALYTICS_COVERAGE,
    SCENARIO_UNIFORM,
    EMAIL_CONFIG_FIELDS,
    EMAIL_TYPES,
    EMAIL_STATUSES,
    DatasetConfig,
)
from operations import bootstrap_dataset, get_dataset_status, setup_django
from scale_preset import BASELINE_STUDENTS, MIN_STUDENTS, MAX_STUDENTS, MAX_VARIATION_PERCENT, scale_preview


GUI_DIR = Path(__file__).resolve().parent / "gui"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 64 * 1024
COUNT_LIMIT = 2_000_000
RESTART_PREPARATION_TIMEOUT_SECONDS = 30.0

COUNT_FIELDS = (
    ("admins", "Admin users", "Login-capable local administrators"),
    ("supervisors", "Supervisor users", "School or programme supervisors"),
    ("mentors", "Mentor users", "Mentors available for group assignment"),
    ("students", "Student users", "Students with profiles and permissions"),
    ("groups", "Groups", "Programme groups and memberships"),
    ("messages", "Chat messages", "Stored messages, including soft-deleted examples"),
    ("login_events", "Login events", "Successful-login audit events"),
    ("tasks", "Tasks", "Group and individual tasks"),
    ("resources", "Resources", "Resource metadata and audiences"),
    (
        "resource_accesses",
        "Resource accesses",
        "Recorded resource access events; the current model does not distinguish action type.",
    ),
    ("announcements", "Announcements", "Published programme announcements"),
    ("deliveries", "Preset announcement batches", "Analytics preset only: adds the same number of system-email batches. Custom mode uses its exact total below."),
    ("events", "Events", "Programme events in several formats"),
    ("rsvps", "RSVPs", "Unique event and user responses"),
)
COUNT_FIELD_NAMES = tuple(name for name, _label, _help in COUNT_FIELDS)
CONFIG_FIELD_NAMES = {*COUNT_FIELD_NAMES, "scenario", "seed", "as_of", *EMAIL_CONFIG_FIELDS}

SCENARIO_METADATA = {
    SCENARIO_ANALYTICS_COVERAGE: {
        "label": "Analytics coverage",
        "description": (
            "Varied deterministic patterns designed to exercise analytics categories "
            "and edge states, including role-targeted and unattributed email deliveries."
        ),
    },
    SCENARIO_UNIFORM: {
        "label": "Uniform",
        "description": (
            "Legacy cyclic distributions for baseline aggregate checks; default "
            "resource counts divide evenly."
        ),
    },
}

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class RequestValidationError(ValueError):
    """A safe, user-facing validation error for a GUI request."""


class JobAlreadyRunningError(RuntimeError):
    """Raised when a second generation job is submitted concurrently."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for variable in ("DB_PASSWORD", "LOCAL_DB_LOGIN_PASSWORD"):
        secret = os.environ.get(variable)
        if secret:
            message = message.replace(secret, "[redacted]")
    return message[:2000]


def _payload_for_gui(payload: dict) -> dict:
    """Copy an API payload and preserve arbitrary-size seeds as decimal strings."""

    result = copy.deepcopy(payload)
    containers = [result]
    manifest = result.get("manifest")
    if isinstance(manifest, dict):
        containers.append(manifest)
    for container in containers:
        config = container.get("config")
        if isinstance(config, dict) and "seed" in config:
            config["seed"] = str(config["seed"])
    return result


def _close_django_connections() -> None:
    try:
        from django.db import connections

        connections.close_all()
    except Exception:
        pass


def build_gui_config(csrf_token: str) -> dict:
    defaults = _payload_for_gui({"config": DatasetConfig().validate().to_manifest()})[
        "config"
    ]
    return {
        "csrf_token": csrf_token,
        "defaults": defaults,
        "count_limit": COUNT_LIMIT,
        "scale_preset": {
            "baseline_students": BASELINE_STUDENTS,
            "min_students": MIN_STUDENTS,
            "max_students": MAX_STUDENTS,
            "max_variation_percent": MAX_VARIATION_PERCENT,
        },
        "email_types": [{"value": value, "label": value.replace('_', ' ').capitalize()} for value in EMAIL_TYPES],
        "email_statuses": [{"value": value, "label": label} for value, label in zip(EMAIL_STATUSES, ('All delivered', 'Partially delivered', 'All failed'))],
        "count_fields": [
            {"name": name, "label": label, "help": help_text}
            for name, label, help_text in COUNT_FIELDS
        ],
        "distribution_fields": [
            {
                "name": "scenario",
                "label": "Scenario",
                "help": "Select the versioned distribution rules used for generated facts.",
                "options": [
                    {"value": value, **SCENARIO_METADATA[value]}
                    for value in DATASET_SCENARIOS
                ],
            },
            {
                "name": "seed",
                "label": "Random seed",
                "help": "Changes deterministic assignments such as interests and message senders.",
            },
            {
                "name": "as_of",
                "label": "Dataset clock (UTC)",
                "help": "Defaults to the current time. Load its config restores the previous snapshot clock for exact replay.",
            },
        ],
    }


def config_from_payload(payload: object) -> DatasetConfig:
    """Strictly parse GUI JSON instead of accepting argv or a shell command."""

    if not isinstance(payload, dict):
        raise RequestValidationError("Request body must be a JSON object.")
    unknown_top_level = set(payload) - {"config", "confirm_replace"}
    if unknown_top_level:
        names = ", ".join(sorted(unknown_top_level))
        raise RequestValidationError(f"Unknown request field(s): {names}.")
    if payload.get("confirm_replace") is not True:
        raise RequestValidationError(
            "Explicit local demo database reset confirmation is required."
        )

    submitted = payload.get("config")
    if not isinstance(submitted, dict):
        raise RequestValidationError("The config field must be a JSON object.")
    unknown_config = set(submitted) - CONFIG_FIELD_NAMES
    if unknown_config:
        names = ", ".join(sorted(unknown_config))
        raise RequestValidationError(f"Unknown configuration field(s): {names}.")
    missing_config = CONFIG_FIELD_NAMES - set(submitted)
    if missing_config:
        names = ", ".join(sorted(missing_config))
        raise RequestValidationError(f"Missing configuration field(s): {names}.")

    values: dict[str, int | str] = {}
    for name in (*COUNT_FIELD_NAMES, 'email_batches', 'email_recipients'):
        value = submitted[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise RequestValidationError(f"{name} must be a whole number.")
        values[name] = value

    for name in ('email_mode', 'email_type', 'email_status', 'email_start', 'email_end'):
        value = submitted[name]
        if not isinstance(value, str) or len(value) > 80:
            raise RequestValidationError(f'{name} must be text of at most 80 characters.')
        values[name] = value.strip()

    scenario = submitted["scenario"]
    if not isinstance(scenario, str) or scenario not in DATASET_SCENARIOS:
        choices = ", ".join(DATASET_SCENARIOS)
        raise RequestValidationError(f"scenario must be one of: {choices}.")
    values["scenario"] = scenario

    seed = submitted["seed"]
    if isinstance(seed, bool):
        raise RequestValidationError("seed must be a whole decimal number.")
    if isinstance(seed, int):
        seed_text = str(seed)
    elif isinstance(seed, str):
        seed_text = seed
    else:
        raise RequestValidationError("seed must be a whole decimal number.")
    if not 0 < len(seed_text) <= 200 or re.fullmatch(
        r"-?(?:0|[1-9][0-9]*)", seed_text
    ) is None:
        raise RequestValidationError(
            "seed must be a whole decimal number of at most 200 characters."
        )
    parsed_seed = int(seed_text)
    values["seed"] = parsed_seed

    as_of = submitted["as_of"]
    if not isinstance(as_of, str) or not as_of.strip() or len(as_of) > 80:
        raise RequestValidationError("as_of must be a timezone-aware ISO-8601 value.")
    values["as_of"] = as_of.strip()

    try:
        return DatasetConfig(**values).validate()
    except (TypeError, ValueError) as exc:
        raise RequestValidationError(str(exc)) from exc


class GenerationJobManager:
    """Keep one generation job active so GUI requests cannot race each other."""

    def __init__(self, runner=bootstrap_dataset):
        self._runner = runner
        self._lock = threading.Lock()
        self._job: dict | None = None
        self._accepting_jobs = True

    def snapshot(self) -> dict:
        with self._lock:
            if self._job is None:
                return {"state": "idle", "messages": []}
            return copy.deepcopy(self._job)

    def start(self, config: DatasetConfig) -> dict:
        with self._lock:
            if not self._accepting_jobs:
                raise JobAlreadyRunningError(
                    "The local database GUI is preparing to restart."
                )
            if self._job and self._job["state"] in {"queued", "running"}:
                raise JobAlreadyRunningError("A dataset generation job is already running.")
            job_id = uuid.uuid4().hex
            self._job = {
                "id": job_id,
                "state": "queued",
                "config": _payload_for_gui({"config": config.to_manifest()})["config"],
                "messages": ["Generation request accepted."],
                "created_at": _now_iso(),
                "started_at": None,
                "finished_at": None,
                "target": None,
                "result": None,
                "error": None,
            }
            snapshot = copy.deepcopy(self._job)

        thread = threading.Thread(
            target=self._run,
            args=(job_id, config),
            name=f"local-db-generator-{job_id[:8]}",
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            with self._lock:
                if self._job and self._job["id"] == job_id:
                    self._job["state"] = "failed"
                    self._job["error"] = _safe_error(exc)
                    self._job["messages"].append(
                        "The background generation worker could not start."
                    )
                    self._job["finished_at"] = _now_iso()
                return copy.deepcopy(self._job)
        return snapshot

    def prepare_for_restart(self) -> dict:
        """Atomically quiesce generation before the launcher restarts the GUI."""

        with self._lock:
            if not self._accepting_jobs:
                raise JobAlreadyRunningError(
                    "A GUI reload is already being prepared."
                )
            if self._job and self._job["state"] in {"queued", "running"}:
                raise JobAlreadyRunningError(
                    "A dataset generation job is already running."
                )
            self._accepting_jobs = False
            return {"state": "ready_for_restart"}

    def _append(self, job_id: str, message: str) -> None:
        with self._lock:
            if self._job and self._job["id"] == job_id:
                self._job["messages"].append(str(message))

    def _run(self, job_id: str, config: DatasetConfig) -> None:
        with self._lock:
            if not self._job or self._job["id"] != job_id:
                return
            self._job["state"] = "running"
            self._job["started_at"] = _now_iso()

        try:
            target, result = self._runner(
                config,
                migration_verbosity=0,
                progress=lambda message: self._append(job_id, message),
            )
        except Exception as exc:
            with self._lock:
                if self._job and self._job["id"] == job_id:
                    self._job["state"] = "failed"
                    self._job["error"] = _safe_error(exc)
                    self._job["messages"].append(
                        "Generation failed. No database reset was committed; "
                        "the previous database contents were preserved."
                    )
                    self._job["finished_at"] = _now_iso()
        else:
            with self._lock:
                if self._job and self._job["id"] == job_id:
                    self._job["state"] = "succeeded"
                    self._job["target"] = target
                    self._job["result"] = _payload_for_gui(result)
                    self._job["finished_at"] = _now_iso()
        finally:
            _close_django_connections()


class LocalDbGuiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    restart_preparation_timeout = RESTART_PREPARATION_TIMEOUT_SECONDS

    def schedule_shutdown_after_restart_prepare(self) -> None:
        """Exit an abandoned quiesced GUI so a later launcher can recover."""

        timer = threading.Timer(self.restart_preparation_timeout, self.shutdown)
        timer.daemon = True
        timer.start()


class LocalDbGuiHandler(BaseHTTPRequestHandler):
    server_version = "BIOTechLocalDbGui/1"
    sys_version = ""
    csrf_token = ""
    manager = GenerationJobManager()
    allowed_origins: set[str] = set()

    def _host_is_allowed(self) -> bool:
        host_header = self.headers.get("Host", "")
        hostname = host_header.rsplit(":", 1)[0].strip("[]").casefold()
        return hostname in {"127.0.0.1", "localhost"}

    def _send_headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        self.end_headers()

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self._send_headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _reject_untrusted_host(self) -> bool:
        if self._host_is_allowed():
            return False
        self._send_json(HTTPStatus.MISDIRECTED_REQUEST, {"error": "Untrusted Host header."})
        return True

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self._reject_untrusted_host():
            return
        path = urlsplit(self.path).path

        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/api/config":
            self._send_json(HTTPStatus.OK, build_gui_config(self.csrf_token))
            return
        if path == "/api/job":
            self._send_json(HTTPStatus.OK, self.manager.snapshot())
            return
        if path == "/api/status":
            try:
                status_payload = _payload_for_gui(get_dataset_status())
            except Exception as exc:
                response_status = HTTPStatus.SERVICE_UNAVAILABLE
                response_payload = {"error": _safe_error(exc)}
            else:
                response_status = HTTPStatus.OK
                response_payload = status_payload
            finally:
                _close_django_connections()
            self._send_json(response_status, response_payload)
            return

        static_file = STATIC_FILES.get(path)
        if static_file is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        filename, content_type = static_file
        try:
            body = (GUI_DIR / filename).read_bytes()
        except OSError:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "GUI asset unavailable."},
            )
            return
        self._send_headers(HTTPStatus.OK, content_type, len(body))
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self._reject_untrusted_host():
            return
        path = urlsplit(self.path).path
        if path not in {"/api/bootstrap", "/api/prepare-restart", "/api/scale-preview"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        origin = self.headers.get("Origin", "")
        if origin not in self.allowed_origins:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "Untrusted request origin."})
            return
        supplied_token = self.headers.get("X-Local-DB-Token", "")
        if not supplied_token or not hmac.compare_digest(supplied_token, self.csrf_token):
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {"error": "Invalid local request token."},
            )
            return
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().casefold()
        if media_type != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON body required."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            content_length = -1
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size."})
            return

        try:
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Malformed JSON body."})
            return

        if path == "/api/scale-preview":
            try:
                response_payload = scale_preview(payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            else:
                self._send_json(HTTPStatus.OK, response_payload)
            return

        if path == "/api/prepare-restart":
            if payload != {"confirm_restart": True}:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Explicit GUI restart confirmation is required."},
                )
                return
            try:
                response_payload = self.manager.prepare_for_restart()
            except JobAlreadyRunningError as exc:
                self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
            else:
                self.server.schedule_shutdown_after_restart_prepare()
                self._send_json(HTTPStatus.OK, response_payload)
                self.wfile.flush()
            return

        try:
            config = config_from_payload(payload)
            job = self.manager.start(config)
        except RequestValidationError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except JobAlreadyRunningError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
        else:
            self._send_json(HTTPStatus.ACCEPTED, job)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
        if self._reject_untrusted_host():
            return
        self._send_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"error": "CORS is not enabled."},
        )

    def log_message(self, format_string: str, *args) -> None:
        print(f"[local-db-gui] {self.address_string()} - {format_string % args}")


def main() -> int:
    setup_django()
    try:
        port = int(os.environ.get("LOCAL_DB_GUI_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise SystemExit("LOCAL_DB_GUI_PORT must be an integer.") from exc
    if not 1024 <= port <= 65535:
        raise SystemExit("LOCAL_DB_GUI_PORT must be between 1024 and 65535.")

    token = secrets.token_urlsafe(32)
    LocalDbGuiHandler.csrf_token = token
    LocalDbGuiHandler.manager = GenerationJobManager()
    LocalDbGuiHandler.allowed_origins = {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }
    server = LocalDbGuiServer(("0.0.0.0", port), LocalDbGuiHandler)
    print(f"Local database GUI ready at http://127.0.0.1:{port}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
