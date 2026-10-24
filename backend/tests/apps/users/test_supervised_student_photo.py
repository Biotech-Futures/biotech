"""A supervisor's student panel: their students' profile photos, which the
supervisor can replace or take off, and when a student agreed to the
policies."""
import io
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.common.role_names import ROLE_STUDENT
from apps.common.storage import reset_managed_storage_caches
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, SupervisorProfile, User


class SupervisedStudentPhotoTests(TestCase):
    def setUp(self):
        self.root = self.enterContext(TemporaryDirectory(prefix="biotech-supervised-photo-test-"))
        self.enterContext(override_settings(MEDIA_ROOT=self.root, USE_AZURE_BLOB_STORAGE=False))
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.student = User.objects.create_user(
            email="amy@example.com", first_name="Amy", last_name="Chen", account_status=User.AccountStatus.ACTIVE,
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=Roles.objects.get_or_create(role_name=ROLE_STUDENT)[0],
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.supervisor = User.objects.create_user(email="grace@school.edu", first_name="Grace", last_name="Green")
        StudentProfile.objects.create(
            user=self.student, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
            parent_guardian_flag=True, school_name="Test High", year_lvl="10",
            supervisor=SupervisorProfile.objects.create(user=self.supervisor, school_name="Test High"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.supervisor)
        self.url = reverse("supervised-student-profile-image", kwargs={"pk": self.student.pk})

    def photo(self):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), "red").save(stream, format="PNG")
        return SimpleUploadedFile("portrait.png", stream.getvalue(), content_type="image/png")

    def test_a_supervisor_replaces_then_removes_their_students_photo(self):
        response = self.client.post(self.url, {"image": self.photo()}, format="multipart")

        self.assertEqual(response.status_code, 200, response.content)
        self.student.refresh_from_db()
        self.assertIn(self.student.profile_image_key, response.json()["profile_image_url"])

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["profile_image_url"])

    def test_not_another_supervisors_student(self):
        stranger = User.objects.create_user(email="other@school.edu", first_name="Olly", last_name="Other")
        SupervisorProfile.objects.create(user=stranger, school_name="Other High")
        self.client.force_authenticate(stranger)

        response = self.client.post(self.url, {"image": self.photo()}, format="multipart")

        self.assertEqual(response.status_code, 403)

    def test_the_roster_gives_each_students_photo_and_when_they_agreed_to_the_policies(self):
        agreed = timezone.now()
        User.objects.filter(pk=self.student.pk).update(policies_agreed_at=agreed)

        row = self.client.get(reverse("supervised-students")).json()[0]

        self.assertIsNone(row["profile_image_url"])
        self.assertIsNotNone(row["policies_agreed_at"])
