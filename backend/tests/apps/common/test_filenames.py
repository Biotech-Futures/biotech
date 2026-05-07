from django.test import SimpleTestCase, override_settings

from apps.chat.utils import reset_pattern_cache
from apps.common.filenames import MAX_FILENAME_LENGTH, sanitize_upload_filename


@override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
class SanitizeUploadFilenameTests(SimpleTestCase):
    def setUp(self):
        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    def test_existing_chat_sanitizer_blacklist_is_reused(self):
        self.assertEqual(
            sanitize_upload_filename("badword-report.pdf"),
            "redacted-report.pdf",
        )

    def test_path_traversal_filename_is_sanitized(self):
        self.assertEqual(
            sanitize_upload_filename("../quarterly-report.pdf"),
            "quarterly-report.pdf",
        )

    def test_html_script_filename_is_sanitized(self):
        self.assertEqual(
            sanitize_upload_filename("../<script>badword</script>.pdf"),
            "redacted.pdf",
        )

    def test_control_characters_are_removed(self):
        self.assertEqual(
            sanitize_upload_filename("report\x00\x1f-name.pdf"),
            "report-name.pdf",
        )

    def test_long_filename_is_truncated_safely(self):
        result = sanitize_upload_filename(f"{'a' * 300}.pdf")
        self.assertLessEqual(len(result), MAX_FILENAME_LENGTH)
        self.assertTrue(result.endswith(".pdf"))

    def test_extension_is_preserved(self):
        self.assertEqual(
            sanitize_upload_filename("badword-report.PDF"),
            "redacted-report.pdf",
        )

    def test_bad_words_are_redacted(self):
        self.assertEqual(
            sanitize_upload_filename("badword-summary.pdf"),
            "redacted-summary.pdf",
        )

    def test_bad_words_are_redacted_case_insensitively(self):
        self.assertEqual(
            sanitize_upload_filename("BaDwOrD-summary.pdf"),
            "redacted-summary.pdf",
        )

    def test_empty_or_unsafe_filename_falls_back(self):
        self.assertEqual(
            sanitize_upload_filename("../<>\x00.pdf"),
            "uploaded-file.pdf",
        )
