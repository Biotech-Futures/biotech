from io import BytesIO
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from apps.admin.services.event_image import upload_event_image


def make_image_upload(
    width=1280,
    height=320,
    image_format="PNG",
    content_type="image/png",
):
    content = BytesIO()
    Image.new("RGB", (width, height), color="green").save(
        content,
        format=image_format,
    )
    return SimpleUploadedFile(
        f"banner.{image_format.lower()}",
        content.getvalue(),
        content_type=content_type,
    )


class UploadEventImageTests(SimpleTestCase):
    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_accepts_and_stores_an_exact_1280_by_320_image(self, get_storage):
        storage = Mock()
        storage.save.return_value = "saved-banner.png"
        get_storage.return_value = storage
        upload = make_image_upload()

        result = upload_event_image(upload)

        self.assertEqual(result["msg"], "Event image uploaded successfully")
        self.assertEqual(result["data"], {"key": "saved-banner.png"})
        storage.save.assert_called_once()
        saved_name, saved_file = storage.save.call_args.args
        self.assertRegex(saved_name, r"^[0-9a-f]{32}\.png$")
        self.assertIs(saved_file, upload)
        self.assertEqual(upload.tell(), 0)

    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_rejects_an_image_with_the_wrong_dimensions(self, get_storage):
        result = upload_event_image(make_image_upload(width=640, height=160))

        self.assertEqual(
            result["msg"],
            "Event banner must be exactly 1280 × 320 pixels with a 4:1 ratio.",
        )
        self.assertIsNone(result["data"])
        get_storage.assert_not_called()

    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_rejects_bytes_that_are_not_a_real_image(self, get_storage):
        upload = SimpleUploadedFile(
            "fake.png",
            b"this is not a PNG",
            content_type="image/png",
        )

        result = upload_event_image(upload)

        self.assertEqual(result["msg"], "The uploaded file is not a valid image.")
        self.assertIsNone(result["data"])
        self.assertEqual(upload.tell(), 0)
        get_storage.assert_not_called()

    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_rejects_an_unsupported_content_type(self, get_storage):
        upload = SimpleUploadedFile(
            "banner.svg",
            b"<svg></svg>",
            content_type="image/svg+xml",
        )

        result = upload_event_image(upload)

        self.assertIn("Unsupported file type", result["msg"])
        self.assertIsNone(result["data"])
        get_storage.assert_not_called()

    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_rejects_a_file_larger_than_five_megabytes(self, get_storage):
        upload = SimpleUploadedFile(
            "large.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )

        result = upload_event_image(upload)

        self.assertEqual(result["msg"], "File too large. Maximum size is 5 MB.")
        self.assertIsNone(result["data"])
        get_storage.assert_not_called()

    @patch("apps.admin.services.event_image.get_event_image_storage")
    def test_returns_a_clear_error_when_storage_fails(self, get_storage):
        storage = Mock()
        storage.save.side_effect = RuntimeError("storage unavailable")
        get_storage.return_value = storage

        result = upload_event_image(make_image_upload())

        self.assertEqual(result["msg"], "Upload failed: storage unavailable")
        self.assertIsNone(result["data"])
