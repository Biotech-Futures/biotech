"""/api/v1/admin/user/<id>/profile-image/: an admin replaces or removes a
user's profile photo from Admin > Users."""
import io
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.common.storage import get_profile_image_storage, reset_managed_storage_caches
from apps.users.models import AdminScope

User = get_user_model()


def photo_url(user_id):
    return f"/api/v1/admin/user/{user_id}/profile-image/"


class AdminProfileImageApiTests(APITestCase):
    def setUp(self):
        self.root = self.enterContext(TemporaryDirectory(prefix="biotech-admin-photo-test-"))
        self.enterContext(override_settings(MEDIA_ROOT=self.root, USE_AZURE_BLOB_STORAGE=False))
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.admin = User.objects.create_user(email="photo.admin@example.com")
        AdminScope.objects.create(user=self.admin)
        self.client.force_authenticate(self.admin)
        self.user = User.objects.create_user(email="pictured@example.com", first_name="Pat", last_name="Lee")

    def photo(self, colour="red"):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), colour).save(stream, format="PNG")
        return SimpleUploadedFile("portrait.png", stream.getvalue(), content_type="image/png")

    def test_an_admin_replaces_then_removes_a_photo(self):
        first = self.client.post(photo_url(self.user.id), {"image": self.photo()}, format="multipart")

        self.assertEqual(first.status_code, 200, first.content)
        self.user.refresh_from_db()
        old_key = self.user.profile_image_key
        self.assertIn(old_key, first.json()["data"]["profileImageUrl"])

        self.client.post(photo_url(self.user.id), {"image": self.photo("blue")}, format="multipart")
        self.user.refresh_from_db()
        self.assertFalse(get_profile_image_storage().exists(old_key))

        removed = self.client.delete(photo_url(self.user.id))

        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertIsNone(removed.json()["data"]["profileImageUrl"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_key, "")
        self.assertEqual(
            list(AuditLog.objects.filter(entity_id=self.user.id).order_by("id").values_list("after_state", flat=True)),
            [{"profile_photo": "replaced"}, {"profile_photo": "replaced"}, {"profile_photo": "removed"}],
        )

    def test_a_file_that_is_not_an_image_is_refused(self):
        fake = SimpleUploadedFile("fake.png", b"\x89PNG\r\n\x1a\nfake bytes", content_type="image/png")

        response = self.client.post(photo_url(self.user.id), {"image": fake}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_key, "")

    def test_only_admins_may_change_it(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(photo_url(self.user.id), {"image": self.photo()}, format="multipart")

        self.assertEqual(response.status_code, 403)
