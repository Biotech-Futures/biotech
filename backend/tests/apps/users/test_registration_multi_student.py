import copy
import io
import json
import uuid
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.common.storage import get_profile_image_storage, reset_managed_storage_caches
from apps.groups.models import GroupInterest, GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    GuardianConsent, KnownUniversity, RegistrationStudent, RegistrationSubmission,
    StudentProfile, StudentSupervisor, SupervisorProfile, User, UserInterest,
)
from apps.users.profile_images import save_profile_image
from tests.apps.users.test_registration_latelink import INTAKE, RegistrationSetup, request_body


def student(index, *, deferred=True, partial=False, grouped=False):
    value = copy.deepcopy(request_body()["payload"]["students"][0])
    value.update(
        firstName=f"Learner{index}", lastName="Example",
        email=f"learner{index}@students.example.test", guardianDeferred=deferred,
        interests=[] if grouped else ["Biotechnology"],
    )
    if partial:
        value.update(school="", yearLevel="", country="", state="")
    if deferred:
        value["guardian"] = {}
    else:
        value["guardian"]["email"] = f"parent{index}@guardians.example.test"
    return value


def batch(journey, count=None, *, offset=0):
    grouped = journey in {"student_team", "supervisor_group"}
    count = count if count is not None else (2 if grouped else 1)
    students = [
        student(
            offset + index, deferred=journey != "student_individual" and not (journey == "student_team" and index == 0),
            partial=journey == "student_team" and index > 0, grouped=grouped,
        ) for index in range(count)
    ]
    payload = {"students": students, "source": {"method": journey}}
    if journey in {"student_individual", "student_team"}:
        original = request_body()["payload"]
        payload.update(supervisor=original["supervisor"])
    if grouped:
        payload["group"] = {"interests": ["Biotechnology", "Engineering"]}
    if journey == "supervisor_csv":
        payload["source"].update(fileName="students.csv", rowNumbers=[2 + index * 2 for index in range(count)])
    return {"journey": journey, "payload": payload}


class MultiStudentSetup(RegistrationSetup):
    def setUp(self):
        super().setUp()
        self.supervisor = User.objects.create_user(
            email="manager@example.test", first_name="Current", last_name="Supervisor",
        )
        self.supervisor.activate()
        self.profile = SupervisorProfile.objects.create(user=self.supervisor, school_name="Current School")
        self.assignment = RoleAssignmentHistory.objects.create(
            user=self.supervisor, role=Roles.objects.get(role_name="supervisor"),
            valid_from=timezone.now() - timedelta(days=1), valid_to=timezone.now() + timedelta(days=30),
        )
        self.supervisor_client = APIClient()
        self.supervisor_client.force_login(self.supervisor)

    def post_batch(self, body, **kwargs):
        client = self.supervisor_client if body["journey"].startswith("supervisor_") else self.client
        return self.submit(body=body, client=client, **kwargs)


class MultiStudentTests(MultiStudentSetup, TestCase):
    def test_all_five_journeys_persist_correlated_receipts_and_pending_students(self):
        journeys = ("student_individual", "student_team", "supervisor_individual", "supervisor_group", "supervisor_csv")
        for offset, journey in enumerate(journeys):
            with self.subTest(journey=journey):
                body = batch(journey, offset=offset * 10)
                response = self.post_batch(body)
                self.assertEqual(response.status_code, 201, response.data)
                submission = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
                self.assertEqual(response.data["journey"], journey)
                self.assertEqual(response.data["student_count"], len(body["payload"]["students"]))
                self.assertEqual(submission.participants.count(), response.data["student_count"])
                self.assertEqual(
                    list(submission.participants.values_list("student__email", flat=True)),
                    [item["email"] for item in body["payload"]["students"]],
                )
                for participant in submission.participants.select_related("student"):
                    user = participant.student
                    self.assertEqual(user.account_status, User.AccountStatus.PENDING)
                    self.assertFalse(user.is_active)
                    self.assertFalse(user.has_usable_password())
                    self.assertFalse(user.studentprofile.has_join_permission)
        self.assertFalse(GuardianConsent.objects.exists())
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())

    def test_group_interests_and_memberships_are_real_not_personal_interest_copies(self):
        body = batch("supervisor_group", 5)
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        submission = RegistrationSubmission.objects.get()
        self.assertTrue(submission.group.group_name.startswith("BTF"))
        self.assertEqual(
            set(GroupInterest.objects.filter(group=submission.group).values_list("interest__interest_desc", flat=True)),
            {"Biotechnology", "Engineering"},
        )
        self.assertEqual(
            GroupMembership.objects.filter(group=submission.group, membership_role="student", left_at=None).count(), 5,
        )
        self.assertTrue(GroupMembership.objects.filter(
            group=submission.group, user=self.supervisor, membership_role="supervisor", left_at=None,
        ).exists())
        self.assertFalse(UserInterest.objects.filter(user__registrationstudent__submission=submission).exists())
        for profile in StudentProfile.objects.all():
            self.assertEqual(profile.supervisor, self.profile)
            self.assertEqual(profile.registered_by, "supervisor")
            self.assertTrue(profile.details_locked)
            self.assertFalse(profile.parent_guardian_flag)
            self.assertIsNone(profile.pg_email)

    def test_identity_only_teammates_have_no_invented_school_country_guardian_or_interests(self):
        response = self.post_batch(batch("student_team", 5))
        self.assertEqual(response.status_code, 201, response.data)
        participants = list(RegistrationSubmission.objects.get().participants.select_related("student"))
        self.assertEqual(participants[0].student.studentprofile.registered_by, "self")
        self.assertTrue(participants[0].student.studentprofile.parent_guardian_flag)
        for participant in participants[1:]:
            user = participant.student
            profile = user.studentprofile
            self.assertIsNone(user.country_id)
            self.assertIsNone(user.state_id)
            self.assertEqual(profile.school_name, "")
            self.assertEqual(profile.year_lvl, "")
            self.assertEqual(profile.pg_first_name, "")
            self.assertEqual(profile.pg_last_name, "")
            self.assertIsNone(profile.pg_email)
            self.assertEqual(profile.registered_by, "peer")
            self.assertFalse(profile.parent_guardian_flag)
            self.assertFalse(profile.details_locked)

    def test_pending_peer_can_complete_details_through_existing_protected_profile_endpoint(self):
        self.assertEqual(self.post_batch(batch("student_team")).status_code, 201)
        peer = User.objects.get(email="learner1@students.example.test")
        client = APIClient()
        client.force_authenticate(peer)
        for data in (
            {"school_name": "Completed High"}, {"year_lvl": "11"},
            {"pg_firstname": "Real"}, {"pg_lastname": "Guardian"},
            {"pg_email": "real.guardian@example.test"},
        ):
            response = client.patch("/api/v1/users/me/", data, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        profile = StudentProfile.objects.get(user=peer)
        self.assertEqual(profile.school_name, "Completed High")
        self.assertEqual(profile.year_lvl, "11")
        self.assertTrue(profile.parent_guardian_flag)
        self.assertFalse(profile.has_join_permission)
        peer.refresh_from_db()
        self.assertEqual(peer.account_status, "pending")

    def test_csv_preserves_row_numbers_and_each_students_intake_metadata(self):
        body = batch("supervisor_csv", 3)
        body["payload"]["students"][1].update(groupingPreference="cross_school", guardianDeferred=False)
        body["payload"]["students"][1]["guardian"] = student(100, deferred=False)["guardian"]
        body["payload"]["students"][1]["guardian"]["phone"] = "+61 400 111 222"
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        submission = RegistrationSubmission.objects.get()
        self.assertEqual(submission.source, {"method": "supervisor_csv", "fileName": "students.csv", "rowNumbers": [2, 4, 6]})
        second = submission.participants.get(position=1)
        self.assertEqual(second.grouping_preference, "cross_school")
        self.assertEqual(second.guardian_phone, "+61 400 111 222")
        self.assertEqual(second.guardian_relationship, "Parent")
        self.assertIsNone(submission.group_id)
        self.assertFalse(Groups.objects.exists())

    def test_supervisor_is_resolved_from_session_and_cannot_be_impersonated(self):
        body = batch("supervisor_individual")
        body["payload"]["supervisor"] = request_body()["payload"]["supervisor"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("supervisor", response.data["fields"])
        body["payload"].pop("supervisor")
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        submission = RegistrationSubmission.objects.get()
        self.assertEqual(submission.created_by, self.supervisor)
        self.assertEqual(submission.supervisor_details["email"], self.supervisor.email)
        self.supervisor.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.supervisor.first_name, "Current")
        self.assertEqual(self.profile.school_name, "Current School")

    def test_supervisor_journeys_require_current_authorized_profile_and_csrf(self):
        for journey in ("supervisor_individual", "supervisor_group", "supervisor_csv"):
            body = batch(journey)
            self.assertEqual(self.submit(body=body).status_code, 403)
            self.assertEqual(self.submit(body=body, client=self.staff_client).status_code, 403)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.supervisor)
        self.assertEqual(self.submit(body=batch("supervisor_csv"), client=client).status_code, 403)
        self.assignment.valid_to = timezone.now() - timedelta(seconds=1)
        self.assignment.save()
        self.assertEqual(self.post_batch(batch("supervisor_csv")).status_code, 403)
        self.assignment.valid_to = timezone.now() + timedelta(days=1)
        self.assignment.save()
        self.supervisor.suspend()
        self.supervisor_client.force_authenticate(self.supervisor)
        self.assertEqual(self.post_batch(batch("supervisor_csv")).status_code, 403)
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_supervisor_group_student_cannot_edit_supervisor_owned_registration_details(self):
        self.assertEqual(self.post_batch(batch("supervisor_group")).status_code, 201)
        user = User.objects.get(email="learner0@students.example.test")
        client = APIClient()
        client.force_authenticate(user)
        response = client.patch("/api/v1/users/me/", {"school_name": "Not permitted"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(StudentProfile.objects.get(user=user).school_name, "Example High")

    def test_duplicate_or_existing_later_email_rolls_back_the_entire_batch(self):
        body = batch("supervisor_group")
        body["payload"]["students"][1]["email"] = body["payload"]["students"][0]["email"].upper()
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.0.email", response.data["fields"])
        self.assertIn("students.1.email", response.data["fields"])
        body = batch("supervisor_group")
        body["payload"]["students"][1]["email"] = self.supervisor.email
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.1.email", response.data["fields"])
        self.assertFalse(StudentProfile.objects.exists())
        self.assertFalse(Groups.objects.exists())
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_guardian_cannot_be_any_student_in_the_batch(self):
        body = batch("student_team")
        body["payload"]["students"][0]["guardian"]["email"] = body["payload"]["students"][1]["email"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.0.guardian.email", response.data["fields"])
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_creator_cannot_defer_guardian_but_represented_students_can(self):
        body = batch("student_team")
        body["payload"]["students"][0].update(guardianDeferred=True, guardian={})
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.0.guardianDeferred", response.data["fields"])
        body = batch("supervisor_individual")
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(StudentProfile.objects.get().parent_guardian_flag)

    def test_all_warnings_are_acknowledged_by_original_student_index(self):
        KnownUniversity.objects.create(name="USYD")
        body = batch("supervisor_csv", 2)
        for item in body["payload"]["students"]:
            item["school"] = "USYD"
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual({item["field"] for item in response.data["warnings"]}, {"students.0.school", "students.1.school"})
        for warning in response.data["warnings"]:
            index = int(warning["override_field"].split(".")[1])
            body["payload"]["students"][index]["overrides"]["ConfirmSchoolOverride"] = True
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["student_count"], 2)

    def test_hard_errors_suppress_warnings_and_no_partial_batch_is_saved(self):
        KnownUniversity.objects.create(name="USYD")
        body = batch("supervisor_csv", 2)
        body["payload"]["students"][0]["school"] = "USYD"
        body["payload"]["students"][1]["email"] = self.supervisor.email
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.1.email", response.data["fields"])
        self.assertNotIn("warnings", response.data)
        self.assertFalse(StudentProfile.objects.exists())

    def test_group_counts_and_individual_counts_match_the_frontend(self):
        for journey, count in (
            ("student_team", 1), ("student_team", 6),
            ("supervisor_group", 1), ("supervisor_group", 6),
            ("supervisor_individual", 2),
        ):
            response = self.post_batch(batch(journey, count))
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("students", response.data["fields"])
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_csv_accepts_500_real_students_but_rejects_501(self):
        response = self.post_batch(batch("supervisor_csv", 501))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentProfile.objects.exists())
        body = batch("supervisor_csv", 500)
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["student_count"], 500)
        self.assertEqual(RegistrationStudent.objects.count(), 500)
        self.assertEqual(StudentProfile.objects.count(), 500)

    def test_csv_source_rows_must_correspond_to_every_included_student(self):
        for rows in ([2], [2, 2], [4, 2], [1, 2]):
            body = batch("supervisor_csv", 2)
            body["payload"]["source"]["rowNumbers"] = rows
            self.assertEqual(self.post_batch(body).status_code, 400)
        body = batch("supervisor_csv")
        body["payload"]["source"]["method"] = "supervisor_individual"
        self.assertEqual(self.post_batch(body).status_code, 400)
        self.assertFalse(RegistrationSubmission.objects.exists())

    def test_unchanged_group_retry_reuses_receipt_and_all_memberships(self):
        body = batch("student_team")
        key = uuid.uuid4()
        first = self.post_batch(body, key=key)
        retry = self.post_batch(body, key=key)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(first.data, retry.data)
        self.assertEqual(Groups.objects.count(), 1)
        self.assertEqual(RegistrationStudent.objects.count(), 2)
        body["payload"]["students"][1]["lastName"] = "Changed"
        self.assertEqual(self.post_batch(body, key=key).status_code, 409)
        self.assertEqual(RegistrationStudent.objects.count(), 2)

    def test_closed_window_and_individual_late_link_do_not_authorize_batches(self):
        invite = self.mint()
        self.close_window()
        for journey in ("student_team", "supervisor_individual", "supervisor_group", "supervisor_csv"):
            for token in ("", invite["token"]):
                response = self.post_batch(batch(journey), token=token)
                self.assertEqual(response.status_code, 400, response.data)
        self.assert_not_consumed(invite)

    def test_a_nominated_supervisor_is_every_members_teacher(self):
        body = batch("student_team")
        nominated = body["payload"]["supervisor"]
        teacher = User.objects.create_user(
            email=nominated["email"], first_name=nominated["firstName"], last_name=nominated["lastName"],
        )
        SupervisorProfile.objects.create(user=teacher, school_name="")
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        relationships = set(StudentSupervisor.objects.values_list("relationship_type", flat=True))
        self.assertEqual(relationships, {StudentSupervisor.RelationshipTypeChoices.TEACHER})


class MultiStudentPhotoTests(MultiStudentSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory(prefix="registration-multi-photo-")
        self.override = override_settings(MEDIA_ROOT=self.media.name, AZURE_PROFILE_IMAGE_CONTAINER="")
        self.override.enable()
        reset_managed_storage_caches()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.override.disable)
        self.addCleanup(reset_managed_storage_caches)

    @staticmethod
    def photo(color="green"):
        output = io.BytesIO()
        Image.new("RGB", (4, 4), color).save(output, "PNG")
        return SimpleUploadedFile("photo.png", output.getvalue(), content_type="image/png")

    def multipart(self, body, *, key=None, second_color="green"):
        return self.supervisor_client.post(INTAKE, {
            "request": json.dumps(body), "students.0": self.photo(),
            "students.1": self.photo(second_color),
        }, format="multipart", HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_each_photo_is_saved_and_later_photo_bytes_bind_idempotency(self):
        body = batch("supervisor_group")
        key = uuid.uuid4()
        first = self.multipart(body, key=key)
        self.assertEqual(first.status_code, 201, first.data)
        participants = RegistrationSubmission.objects.get().participants.select_related("student")
        for item in participants:
            self.assertTrue(get_profile_image_storage().exists(item.student.profile_image_key))
        retry = self.multipart(body, key=key)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(first.data, retry.data)
        self.assertEqual(self.multipart(body, key=key, second_color="blue").status_code, 409)

    def test_later_invalid_photo_has_indexed_error_and_no_partial_writes(self):
        body = batch("supervisor_group")
        response = self.supervisor_client.post(INTAKE, {
            "request": json.dumps(body), "students.0": self.photo(),
            "students.1": SimpleUploadedFile("bad.png", b"not an image", content_type="image/png"),
        }, format="multipart", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data["fields"]["students.1.profilePhoto"], list)
        self.assertFalse(StudentProfile.objects.exists())
        self.assertFalse(Groups.objects.exists())

    def test_later_storage_failure_removes_prior_files_and_rolls_back_every_record(self):
        saved = []

        def fail_second(**kwargs):
            if saved:
                raise OSError("storage unavailable")
            key = save_profile_image(**kwargs)
            saved.append(key)
            return key

        with self.assertLogs("config.exception_handler", level="ERROR"), patch(
            "apps.users.registration_intake.save_profile_image", side_effect=fail_second,
        ):
            response = self.multipart(batch("supervisor_group"))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(get_profile_image_storage().exists(saved[0]))
        self.assertFalse(RegistrationSubmission.objects.exists())
        self.assertFalse(RegistrationStudent.objects.exists())
        self.assertFalse(StudentProfile.objects.exists())
        self.assertFalse(Groups.objects.exists())
