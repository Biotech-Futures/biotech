"""A supervisor registering on the public registration page
(apps.users.supervisor_registration): saved as a mentor is, but active at
once, with their registration email."""
import io
import json
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from apps.common.storage import get_profile_image_storage, reset_managed_storage_caches

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.services import current_cohort
from apps.users.models import (
    MentorProfile, RegistrationSubmission, StudentProfile, StudentSupervisor, SupervisorProfile, User,
)
from apps.users.views import REGISTRATION_PER_IP_LIMIT
from tests.apps.users.test_registration_latelink import INTAKE, RegistrationSetup

SEND = "apps.users.registration_emails.send_system_email"


def supervisor_body(**changes):
    supervisor = {
        "firstName": "Sam", "lastName": "Teacher", "email": "Teacher@Example.com",
        "school": "Example High", "relationship": "teacher", "country": "Australia", "state": "NSW",
        "pronouns": "", "pronounsOther": "", "profilePhoto": None,
    }
    supervisor.update(changes)
    return {"journey": "supervisor", "payload": {"supervisor": supervisor}, "policiesAgreed": True}


class SupervisorRegistrationTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")

    def register(self, body=None, **kwargs):
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            response = self.submit(body=body or supervisor_body(), **kwargs)
        return response, send

    def test_a_supervisor_is_saved_active_with_their_school(self):
        response, send = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        # As a mentor's: a receipt that counts no students.
        self.assertEqual((response.data["journey"], response.data["student_count"]), ("supervisor", 0))

        user = User.objects.get(email="teacher@example.com")
        # Active at once: they sign in as anyone does, to register their students.
        self.assertEqual((user.account_status, user.is_active), (User.AccountStatus.ACTIVE, True))
        self.assertIsNotNone(user.activated_at)
        self.assertFalse(user.has_usable_password())
        self.assertIsNotNone(user.policies_agreed_at)
        self.assertEqual(
            (user.first_name, user.last_name, user.country.country_name, user.state.state_name),
            ("Sam", "Teacher", "Australia", "NSW"),
        )
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(user=user, role__role_name="supervisor", valid_to=None).exists()
        )
        self.assertEqual(SupervisorProfile.objects.get(user=user).school_name, "Example High")
        submission = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual((submission.journey, submission.student, submission.student_count), ("supervisor", user, 0))
        # A teacher, kept as a student's nominated supervisor's mode is.
        self.assertEqual(submission.supervisor_mode, "school")
        self.assertEqual((user.pronouns, user.profile_image_key), ("", ""))
        # Not signed in by registering.
        self.assertNotIn("_auth_user_id", self.client.session)

        # Their registration email, as a mentor's: who it's to and the year.
        send.assert_called_once_with(
            "registration_new_supervisor", "teacher@example.com",
            {"First_Name": "Sam", "YEAR": str(current_cohort())}, background=True,
        )

    def test_what_the_form_asks_for_is_checked_again_here(self):
        left_out = supervisor_body()
        del left_out["payload"]["supervisor"]["school"]
        cases = {
            "supervisor.firstName": supervisor_body(firstName=""),
            "supervisor.lastName": supervisor_body(lastName=""),
            "supervisor.email": supervisor_body(email="not-an-email"),
            # A school is needed, from a parent as from a teacher.
            "supervisor.school": supervisor_body(school=""),
            "supervisor.relationship": supervisor_body(relationship="principal"),
            "supervisor.pronounsOther": supervisor_body(pronouns="Other", pronounsOther=""),
            "supervisor.country": supervisor_body(country=""),
            "supervisor.state": supervisor_body(state=""),
            "supervisor.phone": supervisor_body(phone="0400 000 000"),
        }
        for field, body in [*cases.items(), ("supervisor.school", left_out)]:
            with self.subTest(field=field):
                response, send = self.register(body)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data["fields"])
                send.assert_not_called()
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())
        # Outside Australia, no state is needed.
        response, _ = self.register(supervisor_body(country="New Zealand", state=""))
        self.assertEqual(response.status_code, 201, response.data)

    def test_a_parent_and_their_pronouns(self):
        response, _ = self.register(supervisor_body(relationship="parent", pronouns="Other", pronounsOther="xe/xem"))
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="teacher@example.com")
        self.assertEqual(user.pronouns, "xe/xem")
        self.assertEqual(RegistrationSubmission.objects.get(student=user).supervisor_mode, "parent")
        response, _ = self.register(supervisor_body(email="other@example.com", pronouns="she/her"))
        self.assertEqual(User.objects.get(email="other@example.com").pronouns, "she/her")

    def test_the_policies_are_agreed_to(self):
        body = supervisor_body()
        body["policiesAgreed"] = False
        response, send = self.register(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("policiesAgreed", response.data["fields"])
        send.assert_not_called()
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())

    def test_closed_dates_and_late_links_are_refused(self):
        self.close_window()
        response, send = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Registration is closed. Contact an administrator.")
        send.assert_not_called()
        # Late links are a student's own.
        self.window.closes_at = None
        self.window.save(update_fields=["closes_at"])
        invite = self.mint()
        response, _ = self.register(token=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Late links permit only individual student registration.")
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())

    def test_an_email_with_an_account_is_refused(self):
        supervisor = User.objects.create_user(email="active@example.com", first_name="Ada", last_name="Active")
        SupervisorProfile.objects.create(user=supervisor)
        mentor = User.objects.create_user(email="mentor@example.com", first_name="Men", last_name="Tor")
        MentorProfile.objects.create(user=mentor, max_group_count=1)
        for email in ("active@example.com", "mentor@example.com", "staff@example.com"):
            with self.subTest(email=email):
                response, send = self.register(supervisor_body(email=email.upper()))
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(
                    response.data["fields"]["supervisor.email"], ["An account with this email already exists."],
                )
                send.assert_not_called()

    def test_the_same_request_sent_again_gets_the_same_receipt(self):
        key = uuid.uuid4()
        first, _ = self.register(key=key)
        self.assertEqual(first.status_code, 201, first.data)
        again, send = self.register(key=key)
        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual(again.data, first.data)
        send.assert_not_called()
        # A changed request with the same key is refused.
        changed, _ = self.register(supervisor_body(firstName="Samantha"), key=key)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(User.objects.filter(email="teacher@example.com").count(), 1)

    def test_each_registration_counts_toward_the_per_ip_limit(self):
        for index in range(REGISTRATION_PER_IP_LIMIT):
            response, _ = self.register(supervisor_body(email=f"teacher{index}@example.com"))
            self.assertEqual(response.status_code, 201, response.data)
        response, _ = self.register(supervisor_body(email="one-more@example.com"))
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(email="one-more@example.com").exists())

    def test_signed_in_they_register_their_students(self):
        self.register()
        self.client.force_login(User.objects.get(email="teacher@example.com"))
        self.body["journey"] = "supervisor_individual"
        del self.body["payload"]["supervisor"]
        self.body["payload"]["source"] = {"method": "supervisor_individual"}
        self.body["payload"]["students"][0]["email"] = "pupil@example.com"
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            StudentProfile.objects.get(user__email="pupil@example.com").supervisor.user.email, "teacher@example.com",
        )

    def test_students_who_named_them_before_they_registered_become_theirs(self):
        # A student registers, naming the teacher before they have an account.
        self.assertEqual(self.submit().status_code, 201)
        named = StudentProfile.objects.get(user__email="jordan.lee@example.com")
        self.assertIsNone(named.supervisor)
        # One who named them but has a supervisor already keeps theirs.
        other = User.objects.create_user(email="other@example.com", first_name="O", last_name="T")
        other_profile = SupervisorProfile.objects.create(user=other)
        self.body["payload"]["students"][0]["email"] = "kept@example.com"
        self.assertEqual(self.submit().status_code, 201)
        StudentProfile.objects.filter(user__email="kept@example.com").update(supervisor=other_profile)

        response, _ = self.register(supervisor_body(relationship="parent"))
        self.assertEqual(response.status_code, 201, response.data)
        profile = SupervisorProfile.objects.get(user__email="teacher@example.com")
        named.refresh_from_db()
        self.assertEqual(named.supervisor, profile)
        # As their parent, as the supervisor said.
        self.assertTrue(
            StudentSupervisor.objects.filter(
                student_user=named, supervisor_user=profile,
                relationship_type=StudentSupervisor.RelationshipTypeChoices.PARENT_GUARDIAN,
            ).exists()
        )
        self.assertEqual(StudentProfile.objects.get(user__email="kept@example.com").supervisor, other_profile)


class SupervisorPhotoTests(RegistrationSetup, TestCase):
    """A supervisor's photo, sent as a student's is."""

    def setUp(self):
        super().setUp()
        self.root = self.enterContext(TemporaryDirectory(prefix="biotech-supervisor-test-"))
        self.enterContext(override_settings(MEDIA_ROOT=self.root, USE_AZURE_BLOB_STORAGE=False))
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

    def photo(self, content=None):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), "red").save(stream, format="PNG")
        return SimpleUploadedFile("portrait.png", content or stream.getvalue(), content_type="image/png")

    def upload(self, body, files):
        with patch(SEND), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                INTAKE, {"request": json.dumps(body), **files}, format="multipart",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            )

    def test_their_photo_is_saved(self):
        photo = self.photo()
        body = supervisor_body(profilePhoto={"name": "portrait.png", "type": "image/png", "size": photo.size})
        response = self.upload(body, {"supervisor": photo})
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="teacher@example.com")
        self.assertEqual(user.profile_image_content_type, "image/png")
        self.assertTrue(get_profile_image_storage().exists(user.profile_image_key))

    def test_only_a_real_image_in_its_own_field(self):
        metadata = {"name": "portrait.png", "type": "image/png", "size": 10}
        cases = [
            # Not an image.
            ({"supervisor": self.photo(b"not an image at all")}, "supervisor.profilePhoto"),
            # Its metadata with no file.
            ({}, "supervisor.profilePhoto"),
            # A student's field.
            ({"students.0": self.photo()}, "error"),
        ]
        for files, field in cases:
            with self.subTest(field=field, files=list(files)):
                response = self.upload(supervisor_body(profilePhoto=metadata), files)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data.get("fields", response.data))
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())
