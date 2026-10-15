import logging
import os
import threading
from unittest import mock

from django.db import DataError, DatabaseError, OperationalError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.system_logs import handler as handler_module
from apps.system_logs.handler import DatabaseLogHandler, _Writer, build_row, is_wanted
from apps.system_logs.models import SystemLogEntry
from apps.system_logs.redaction import REDACTED

ENABLED = override_settings(
    SYSTEM_LOG_DB_ENABLED=True,
    SYSTEM_LOG_DISPATCH_SYNC=True,
    SYSTEM_LOG_DB_LEVEL="WARNING",
    SYSTEM_LOG_DB_INFO_LOGGERS=("apps.services.mailer",),
)


def _record(name="apps.example", level=logging.WARNING, msg="hello %s", args=("world",), exc_info=None, **extra):
    record = logging.LogRecord(name, level, __file__, 10, msg, args, exc_info)
    record.__dict__.update(extra)
    return record


@ENABLED
class IsWantedTests(SimpleTestCase):
    def test_keeps_warning_and_above_from_any_logger(self):
        self.assertTrue(is_wanted(_record(level=logging.WARNING)))
        self.assertTrue(is_wanted(_record(level=logging.ERROR)))

    def test_keeps_info_only_from_the_allowlist_and_its_children(self):
        self.assertTrue(is_wanted(_record("apps.services.mailer", logging.INFO)))
        self.assertTrue(is_wanted(_record("apps.services.mailer.pool", logging.INFO)))
        self.assertFalse(is_wanted(_record("apps.services.mailerx", logging.INFO)))
        self.assertFalse(is_wanted(_record("config.exception_handler", logging.INFO)))

    def test_never_keeps_debug(self):
        self.assertFalse(is_wanted(_record("apps.services.mailer", logging.DEBUG)))

    def test_never_keeps_database_or_own_loggers(self):
        self.assertFalse(is_wanted(_record("django.db.backends", logging.ERROR)))
        self.assertFalse(is_wanted(_record("apps.system_logs.handler", logging.ERROR)))

    def test_never_keeps_server_access_logs_or_their_children(self):
        for name in (
            "django.server",
            "django.channels.server",
            "daphne.server",
            "daphne.http_protocol",
            "uvicorn.access",
            "gunicorn.access",
            "uvicorn.access.child",
        ):
            for level in (logging.WARNING, logging.ERROR):
                with self.subTest(logger=name, level=level):
                    self.assertFalse(is_wanted(_record(name, level)))

    def test_keeps_django_request_errors_and_server_error_loggers(self):
        # django.request is how Django reports 5xx responses; the servers'
        # error loggers report worker timeouts and crashes, not requests.
        for name in ("django.request", "uvicorn.error", "gunicorn.error"):
            with self.subTest(logger=name):
                self.assertTrue(is_wanted(_record(name, logging.ERROR)))

    def test_exclusions_match_whole_logger_names_only(self):
        # A logger that merely starts with the same letters is not a child.
        self.assertTrue(is_wanted(_record("django.serverless", logging.WARNING)))
        self.assertTrue(is_wanted(_record("uvicorn.accessibility", logging.WARNING)))

    @override_settings(SYSTEM_LOG_DB_ENABLED=False)
    def test_off_switch(self):
        self.assertFalse(is_wanted(_record(level=logging.CRITICAL)))

    @override_settings(SYSTEM_LOG_DB_LEVEL="ERROR")
    def test_level_is_configurable(self):
        self.assertFalse(is_wanted(_record(level=logging.WARNING)))
        self.assertTrue(is_wanted(_record(level=logging.ERROR)))


class BuildRowTests(SimpleTestCase):
    def test_formats_message_and_traceback_as_text(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            row = build_row(_record(exc_info=sys.exc_info()))
        self.assertEqual(row["message"], "hello world")
        self.assertIn("ValueError: boom", row["traceback"])
        self.assertEqual(row["level_name"], "WARNING")
        self.assertEqual(row["logger_name"], "apps.example")

    def test_redacts_message_and_extra(self):
        row = build_row(_record(msg="reset link https://x.org/r?token=abc", args=(), sid="session-key", user_id=3))
        self.assertNotIn("abc", row["message"])
        self.assertEqual(row["extra"]["sid"], REDACTED)
        self.assertEqual(row["extra"]["user_id"], 3)

    def test_survives_arguments_that_dont_fit_the_message(self):
        row = build_row(_record(msg="%s and %s", args=("one",)))
        self.assertEqual(row["message"], "%s and %s")

    def test_keeps_status_code_from_django_request_records(self):
        self.assertEqual(build_row(_record(status_code=503))["status_code"], 503)
        self.assertIsNone(build_row(_record(status_code="bad"))["status_code"])

    def test_has_no_request_details_outside_a_request(self):
        row = build_row(_record())
        self.assertEqual((row["request_id"], row["request_path"], row["user_id"]), ("", "", None))


@ENABLED
class HandlerTests(TestCase):
    def setUp(self):
        self.logger = logging.getLogger("apps.example.handler_tests")
        self.logger.propagate = False
        self.handler = DatabaseLogHandler(level=logging.INFO)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)

    def test_keeps_a_wanted_record(self):
        self.logger.warning("disk %s", "full")

        entry = SystemLogEntry.objects.get()
        self.assertEqual(entry.message, "disk full")
        self.assertEqual(entry.level, logging.WARNING)

    def test_ignores_an_unwanted_record(self):
        self.logger.info("routine")
        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_ignores_daphne_runserver_request_lines(self):
        # Exactly what daphne's runserver logged for a 400 in local testing.
        server_logger = logging.getLogger("django.channels.server")
        server_logger.addHandler(self.handler)
        self.addCleanup(server_logger.removeHandler, self.handler)

        server_logger.warning("\x1b[31;1mHTTP POST /services/verify-login-code/ 400 [5.02, 127.0.0.1:55573]\x1b[0m")

        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_saves_messages_and_tracebacks_without_colour_codes(self):
        try:
            raise ValueError("\x1b[33mcoloured failure\x1b[0m")
        except ValueError:
            self.logger.exception("\x1b[31;1mrequest failed\x1b[0m")

        entry = SystemLogEntry.objects.get()
        self.assertEqual(entry.message, "request failed")
        self.assertIn("ValueError: coloured failure", entry.traceback)
        self.assertNotIn("\x1b", entry.message + entry.traceback)

    def test_database_failure_never_reaches_the_caller(self):
        with mock.patch.object(handler_module, "write_now", side_effect=DatabaseError("db down")):
            self.logger.error("still fine")  # must not raise
        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_failed_write_leaves_the_callers_transaction_usable(self):
        with mock.patch.object(SystemLogEntry.objects, "create", side_effect=DatabaseError("db down")):
            self.logger.error("lost")
        # A query in the same (test) transaction still works.
        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_logging_during_a_write_does_not_recurse(self):
        calls = []

        def write_and_log(row):
            calls.append(row)
            self.logger.error("logged while writing")

        with mock.patch.object(handler_module, "write_now", side_effect=write_and_log):
            self.logger.error("first")
        self.assertEqual(len(calls), 1)

    @override_settings(SYSTEM_LOG_DISPATCH_SYNC=False)
    def test_queues_instead_of_writing_when_not_sync(self):
        with mock.patch.object(handler_module._writer, "submit") as submit, \
                mock.patch.object(handler_module, "write_now") as write_now:
            self.logger.error("queued")
        submit.assert_called_once()
        write_now.assert_not_called()
        self.assertEqual(submit.call_args.args[0]["message"], "queued")


def _row(message="m"):
    return {"created_at": None, "level": 30, "level_name": "WARNING", "logger_name": "x", "message": message}


class WriterBatchTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.object(handler_module, "_close_connection")
        self.close_connection = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch("django.db.close_old_connections")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reconnects_and_retries_after_a_dropped_connection(self):
        with mock.patch.object(SystemLogEntry.objects, "bulk_create", side_effect=[OperationalError("gone"), None]) as bulk:
            _Writer.write_batch([_row()])
        self.assertEqual(bulk.call_count, 2)
        self.close_connection.assert_called()

    def test_gives_up_after_one_retry_without_raising(self):
        with mock.patch.object(SystemLogEntry.objects, "bulk_create", side_effect=OperationalError("gone")) as bulk, \
                mock.patch.object(handler_module, "_report") as report:
            _Writer.write_batch([_row()])
        self.assertEqual(bulk.call_count, 2)
        report.assert_called_once()

    def test_skips_only_the_rows_the_database_refuses(self):
        saved = []

        def create(**row):
            if row["message"] == "bad":
                raise DataError("too long")
            saved.append(row["message"])

        with mock.patch.object(SystemLogEntry.objects, "bulk_create", side_effect=DataError("too long")), \
                mock.patch.object(SystemLogEntry.objects, "create", side_effect=create), \
                mock.patch.object(handler_module, "_report"):
            _Writer.write_batch([_row("good"), _row("bad"), _row("also good")])
        self.assertEqual(saved, ["good", "also good"])


class WriterThreadTests(SimpleTestCase):
    def _writer(self):
        writer = _Writer()
        written = []
        done = threading.Event()

        def write_batch(batch, **kwargs):
            written.extend(batch)
            done.set()

        writer.write_batch = write_batch
        return writer, written, done

    def test_starts_lazily_and_writes_queued_rows_on_its_own_thread(self):
        writer, written, done = self._writer()
        self.assertIsNone(writer.pid)

        with mock.patch.object(handler_module, "_close_connection"):
            writer.submit(_row("queued"))
            self.assertTrue(done.wait(5))
        self.assertEqual(writer.pid, os.getpid())
        self.assertEqual([row["message"] for row in written], ["queued"])

    def test_starts_a_new_queue_in_a_forked_process(self):
        writer, _, done = self._writer()
        with mock.patch.object(handler_module, "_close_connection"):
            writer.submit(_row())
            done.wait(5)
            first_queue = writer.queue

            # What a gunicorn worker sees after fork: the parent's pid.
            writer.after_fork_in_child()
            writer.pid = -1
            writer.submit(_row())
        self.assertIsNot(writer.queue, first_queue)
        self.assertEqual(writer.pid, os.getpid())

    def test_full_queue_drops_and_counts_instead_of_blocking(self):
        writer = _Writer()
        writer.pid = os.getpid()
        import queue

        writer.queue = queue.Queue(maxsize=1)
        writer.submit(_row())
        writer.submit(_row())  # must not block
        self.assertEqual(writer.dropped, 1)
