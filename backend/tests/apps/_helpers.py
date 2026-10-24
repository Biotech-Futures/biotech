from unittest.mock import patch

from django.core.signals import request_finished
from django.db import close_old_connections


def close_response(response):
    """Closes a response, letting go of any file it streams, the way Django's
    test client closes one. ``response.close()`` alone also runs
    ``close_old_connections``, which on Postgres closes the connection the
    test's transaction is on, and every later test in the class then fails
    with "the connection is closed". SQLite in memory never closes, so only
    the Postgres run shows it."""
    request_finished.disconnect(close_old_connections)
    try:
        response.close()
    finally:
        request_finished.connect(close_old_connections)


class ConsumerConnectionMixin:
    """For a TestCase that runs Channels consumers. ``database_sync_to_async``
    runs ``close_old_connections`` before and after each call, as a request
    does, and called through ``async_to_sync`` that is the test's own
    connection: see ``close_response`` for what that does on Postgres.
    Channels' own test communicator does the same, but only while it sends
    or receives.

    In setUpClass, which a TestCase always chains, unlike setUp."""

    @classmethod
    def setUpClass(cls):
        patcher = patch("channels.db.close_old_connections")
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        super().setUpClass()


def assert_public_message_shape(testcase, payload):
    testcase.assertIn("id", payload)
    testcase.assertIn("sender_name", payload)
    testcase.assertIn("message_text", payload)
    testcase.assertIn("message_type", payload)
    testcase.assertIn("sent_at", payload)
    testcase.assertIn("edited_at", payload)
    testcase.assertIn("deleted_at", payload)
    testcase.assertIn("deleted_by", payload)
    testcase.assertIn("deleted_by_name", payload)
    testcase.assertIn("is_deleted", payload)
    testcase.assertIn("is_edited", payload)
    testcase.assertIn("attachments", payload)
    testcase.assertIn("resources", payload)
    testcase.assertNotIn("group", payload)
    testcase.assertNotIn("sender_user", payload)
    testcase.assertNotIn("sender_id", payload)
    testcase.assertNotIn("text", payload)
    testcase.assertNotIn("resource_ids", payload)


class StorageCleanupMixin:
    storage_attr = ""
    storage_keys_attr = ""

    def tearDown(self):
        storage = getattr(self, self.storage_attr, None)
        for storage_key in getattr(self, self.storage_keys_attr, []):
            if storage_key and storage is not None and storage.exists(storage_key):
                # On Windows, ``FileResponse`` may still hold the file open
                # when tearDown runs (POSIX lets you unlink an open file;
                # Windows does not). The cleanup is best-effort — leftover
                # bytes live under ``backend/media/`` which is gitignored —
                # so swallow OSError instead of failing an otherwise-passing
                # test on the lock.
                try:
                    storage.delete(storage_key)
                except OSError:
                    pass
        super().tearDown()
