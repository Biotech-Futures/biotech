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
