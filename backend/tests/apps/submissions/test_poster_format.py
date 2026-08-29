"""The poster format checks as the upload endpoint applies them.

The checks themselves are covered in ``test_poster_checks``. What is tested
here is the wiring: that a wrongly-shaped poster is refused with something a
student can act on, that a correct one is stored along with what was found, and
that the finding travels with the entry when it is submitted.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission, SubmissionQuestion
from apps.submissions.poster_checks import SUPERVISOR_EMAIL, TEAM_CODE
from apps.users.models import User

from .seed_data import install_question_set
from .test_poster_checks import A2, TEMPLATE, US_LETTER, _build_pdf


def _upload_file(width, height, *, text="", pages=1, name="poster.pdf"):
    return SimpleUploadedFile(
        name,
        _build_pdf(width, height, text=text, pages=pages),
        content_type="application/pdf",
    )


@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True)
class PosterFormatUploadTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        role = Roles.objects.create(role_name="student")
        # The group name is the team code the poster is expected to carry, so
        # it has to look like a real one rather than a description.
        self.group = Groups.objects.create(group_name="BTF7")
        self.student = User.objects.create_user(
            email="poster@test.local", password="testUser@123",
            first_name="Poster", last_name="Student",
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=self.student, membership_role="student"
        )
        install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)
        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse(
            "group-submission-submit", kwargs={"group_id": self.group.id}
        )
        self.poster_url = reverse(
            "group-submission-file",
            kwargs={"group_id": self.group.id, "slot": "poster"},
        )

    def _upload(self, upload):
        return self.client.post(self.poster_url, {"file": upload}, format="multipart")

    def _submission(self):
        return Submission.objects.get(group=self.group)

    # ------------------------------------------------------------- refusing
    def test_a_landscape_poster_is_refused_and_not_stored(self):
        response = self._upload(_upload_file(A2[1], A2[0]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "poster_format_rejected")
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_a_landscape_poster_is_told_plainly_that_it_is_landscape(self):
        # Orientation is obvious on sight, so saying so is reporting a fact
        # back rather than making a judgement the student cannot check.
        problems = " ".join(self._upload(_upload_file(A2[1], A2[0])).data["problems"])

        self.assertIn("portrait", problems.lower())
        self.assertIn("landscape", problems.lower())

    def test_a_wrongly_shaped_page_gets_a_general_instruction_not_our_arithmetic(self):
        # US Letter is portrait and looks like a normal page. The only thing
        # wrong with it is a ratio, which the student cannot measure — so they
        # are pointed at the template rather than told a number.
        problems = " ".join(self._upload(_upload_file(*US_LETTER)).data["problems"])

        self.assertIn("poster template", problems)
        self.assertNotIn("ratio", problems.lower())
        self.assertNotIn("tolerance", problems.lower())

    def test_a_multi_page_pdf_is_refused(self):
        response = self._upload(_upload_file(*A2, pages=2))

        self.assertEqual(response.status_code, 400)
        self.assertIn("single page", " ".join(response.data["problems"]).lower())

    # ------------------------------------------------------------ accepting
    def test_a_poster_built_from_the_programmes_template_is_accepted(self):
        # The size the programme's own PowerPoint template produces, which is
        # not A2. Refusing this would refuse nearly every real submission.
        response = self._upload(_upload_file(*TEMPLATE, text="BTF7 a@b.edu.au"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self._submission().poster)

    def test_a_complete_poster_is_recorded_with_no_warnings(self):
        self._upload(_upload_file(*TEMPLATE, text="BTF7 supervisor@school.edu.au"))

        flag = self._submission().poster_checks
        self.assertEqual(flag["warnings"], [])
        self.assertTrue(flag["has_text"])

    def test_a_poster_missing_its_team_code_is_accepted_but_flagged(self):
        # The whole point of the soft half: it goes through, and says so.
        response = self._upload(_upload_file(*TEMPLATE, text="a@b.edu.au only"))

        self.assertEqual(response.status_code, 200)
        codes = {w["code"] for w in self._submission().poster_checks["warnings"]}
        self.assertEqual(codes, {TEAM_CODE})

    def test_a_poster_with_no_text_layer_is_accepted_without_warnings(self):
        response = self._upload(_upload_file(*TEMPLATE))

        self.assertEqual(response.status_code, 200)
        flag = self._submission().poster_checks
        self.assertFalse(flag["has_text"])
        self.assertEqual(flag["warnings"], [])

    def test_an_unreadable_pdf_is_allowed_through_rather_than_refused(self):
        upload = SimpleUploadedFile(
            "poster.pdf", b"%PDF-1.7\nnot really\n%%EOF\n", content_type="application/pdf"
        )

        response = self._upload(upload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._submission().poster_checks["unreadable"])

    # -------------------------------------------------------- staying in step
    def test_replacing_the_poster_replaces_what_was_found_about_it(self):
        self._upload(_upload_file(*TEMPLATE, text="nothing useful"))
        self.assertTrue(self._submission().poster_checks["warnings"])

        self._upload(_upload_file(*TEMPLATE, text="BTF7 supervisor@school.edu.au"))

        self.assertEqual(self._submission().poster_checks["warnings"], [])

    def test_removing_the_poster_clears_what_was_found_about_it(self):
        self._upload(_upload_file(*TEMPLATE, text="nothing useful"))

        self.client.delete(self.poster_url)

        self.assertIsNone(self._submission().poster_checks)

    def test_the_finding_is_frozen_with_the_entry_when_it_is_submitted(self):
        self._upload(_upload_file(*TEMPLATE, text="a@b.edu.au but no code"))
        self.client.put(
            self.detail_url,
            {"answers": {q.key: "An answer." for q in SubmissionQuestion.active()}},
            format="json",
        )

        self.assertEqual(
            self.client.post(self.submit_url, {}, format="json").status_code, 200
        )

        submission = self._submission()
        codes = {w["code"] for w in submission.submitted_poster_checks["warnings"]}
        self.assertEqual(codes, {TEAM_CODE})

    def test_the_page_is_told_what_was_found(self):
        self._upload(_upload_file(*TEMPLATE, text="BTF7 only"))

        payload = self.client.get(self.detail_url).data

        codes = {w["code"] for w in payload["submission"]["poster_checks"]["warnings"]}
        self.assertEqual(codes, {SUPERVISOR_EMAIL})

    def test_the_recorded_finding_keeps_the_detail_the_student_is_spared(self):
        # The two audiences differ on purpose: the student is pointed at the
        # template, while whoever reviews the entry can still see exactly which
        # check failed and why.
        self._upload(_upload_file(*TEMPLATE, text="no code here"))

        warnings = self._submission().poster_checks["warnings"]
        self.assertTrue(warnings)
        self.assertTrue(all(w["message"] for w in warnings), "detail was dropped")
