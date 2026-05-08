def assert_public_message_shape(testcase, payload):
    testcase.assertIn("id", payload)
    testcase.assertIn("sender_name", payload)
    testcase.assertIn("message_text", payload)
    testcase.assertIn("message_type", payload)
    testcase.assertIn("sent_at", payload)
    testcase.assertIn("edited_at", payload)
    testcase.assertIn("is_edited", payload)
    testcase.assertIn("attachments", payload)
    testcase.assertIn("resources", payload)
    testcase.assertNotIn("group", payload)
    testcase.assertNotIn("sender_user", payload)
    testcase.assertNotIn("deleted_at", payload)
    testcase.assertNotIn("is_deleted", payload)
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
                storage.delete(storage_key)
        super().tearDown()
