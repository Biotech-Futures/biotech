"""Student and supervisor read views behind the release gates: my grades,
summary/certificate downloads, and the supervisor bundle."""
import io
import zipfile
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import (
    CertificatesRelease,
    FinalistFlag,
    Grade,
    GradingJob,
    MarksRelease,
)
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.users.models import User

from .fixtures import _GradingFixture, _seed_doc_templates


class StudentReadViewsTests(_GradingFixture):
    """Release gate: pre-release → 403; post-release → own group only."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.student_user = User.objects.create_user(
            email="stud@example.com", first_name="Sam", last_name="Student",
            password="pw12345!", is_staff=False,
        )
        # Join the fixture group as a student.
        GroupMembership.objects.create(
            group=cls.group, user=cls.student_user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        # Seed one released grade so the docx render has real numbers.
        Grade.objects.create(
            submission=cls.saq_submission, criterion=cls.saq_c1,
            mark=Decimal("8.00"), comment="Great",
        )

    def setUp(self):
        self.client = APIClient()
        MarksRelease.load()  # ensure row exists; released_at stays None by default

    def _release_now(self):
        rel = MarksRelease.load()
        rel.released_at = timezone.now()
        rel.released_by = self.staff
        rel.save()

    def _release_certificates_now(self):
        rel = CertificatesRelease.load()
        rel.released_at = timezone.now()
        rel.released_by = self.staff
        rel.save()

    def test_pre_release_denied(self):
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-grades"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_release_returns_own_grades(self):
        self._release_now()
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-grades"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertEqual(data["group"]["id"], self.group.id)
        saq = next(c for c in data["components"] if c["code"] == "SAQ")
        self.assertEqual(saq["criteria"][0]["mark"], "8.00")

    def test_summary_docx_streams(self):
        _seed_doc_templates()
        self._release_now()
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-summary"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("wordprocessingml", r["Content-Type"])
        # docx = zip file; magic bytes PK\x03\x04
        self.assertTrue(r.content[:4] == b"PK\x03\x04")

    def test_certificate_docx_streams(self):
        # Certificates have their own gate — marks being released is neither
        # necessary nor sufficient.
        _seed_doc_templates()
        self._release_now()
        self.client.force_authenticate(self.student_user)
        self.assertEqual(
            self.client.get(reverse("grading:me-certificate")).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self._release_certificates_now()
        r = self.client.get(reverse("grading:me-certificate"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.content[:4] == b"PK\x03\x04")

    def test_no_submission_no_marks_or_certificate(self):
        """Even after release, teams that never submitted see nothing."""
        self._release_now()
        self._release_certificates_now()
        lurker = User.objects.create_user(
            email="lurker@example.com", first_name="Lu", last_name="Rker",
            password="pw12345!",
        )
        empty_group = Groups.objects.create(group_name="BTF-EMPTY-1")
        GroupMembership.objects.create(
            group=empty_group, user=lurker,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.client.force_authenticate(lurker)
        for name in ("grading:me-grades", "grading:me-summary", "grading:me-certificate"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, name)
            self.assertIn("did not submit", r.json()["detail"])

    @override_settings(GRADING_JOB_DISPATCH_SYNC=True)
    def test_supervisor_bundle_adapts_to_release_gates(self):
        from django.core.files.storage import default_storage

        from apps.users.models import StudentProfile, SupervisorProfile

        _seed_doc_templates()

        supervisor = User.objects.create_user(
            email="super@example.com", first_name="Sue", last_name="Pervisor",
            password="pw12345!",
        )
        profile = SupervisorProfile.objects.create(user=supervisor, school_name="Test School")
        StudentProfile.objects.create(
            user=self.student_user, pg_first_name="P", pg_last_name="G",
            supervisor=profile, school_name="Test School", year_lvl="11",
        )

        def bundle_names():
            resp = self.client.post(reverse("grading:supervisor-download"), {}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.content)
            job = GradingJob.objects.get(pk=resp.json()["job_id"])
            self.assertEqual(job.status, GradingJob.STATUS_DONE, job.error)
            with default_storage.open(job.result_url, "rb") as fh:
                return set(zipfile.ZipFile(io.BytesIO(fh.read())).namelist())

        self.client.force_authenticate(supervisor)

        # Neither gate open -> the endpoint itself refuses.
        self.assertEqual(
            self.client.post(reverse("grading:supervisor-download"), {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Marks only -> summaries, no certificates.
        self._release_now()
        names = bundle_names()
        self.assertTrue(any(n.endswith("marks-summary.docx") for n in names), names)
        self.assertFalse(any(n.endswith("certificate.docx") for n in names), names)

        # Certificates too -> both documents.
        self._release_certificates_now()
        names = bundle_names()
        self.assertTrue(any(n.endswith("marks-summary.docx") for n in names), names)
        self.assertTrue(any(n.endswith("certificate.docx") for n in names), names)

    def test_certificates_release_toggle(self):
        self.client.force_authenticate(self.staff)
        url = reverse("grading:certificates-release")
        r = self.client.get(url)
        self.assertIsNone(r.json()["released_at"])

        r = self.client.post(url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.json()["released_at"])
        # Marks gate untouched by the certificates toggle.
        self.assertIsNone(MarksRelease.load().released_at)

        r = self.client.post(url, {"release": "false"}, format="json")
        self.assertIsNone(r.json()["released_at"])

    def test_exclusion_is_on_by_default(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:certificates-release"))
        self.assertTrue(r.json()["exclude_finalists"])

    def test_exclusion_only_post_does_not_restamp_release(self):
        self.client.force_authenticate(self.staff)
        url = reverse("grading:certificates-release")
        released_at = self.client.post(url, {}, format="json").json()["released_at"]

        r = self.client.post(url, {"exclude_finalists": "true"}, format="json")
        self.assertTrue(r.json()["exclude_finalists"])
        self.assertEqual(r.json()["released_at"], released_at)

        r = self.client.post(url, {"exclude_finalists": "false"}, format="json")
        self.assertFalse(r.json()["exclude_finalists"])
        self.assertEqual(r.json()["released_at"], released_at)

    def test_supervisor_grades_listing_by_release_and_group(self):
        """GET /supervisor/students/grades/ — gate, rows, and the group-less
        student branch, all in one released-world walk-through."""
        from apps.users.models import StudentProfile, SupervisorProfile

        supervisor = User.objects.create_user(
            email="listing-super@example.com", first_name="Sue", last_name="Pervisor",
            password="pw12345!",
        )
        profile = SupervisorProfile.objects.create(user=supervisor, school_name="Test School")
        StudentProfile.objects.create(
            user=self.student_user, pg_first_name="P", pg_last_name="G",
            supervisor=profile, school_name="Test School", year_lvl="11",
        )
        # A supervised student who never joined a group must still appear,
        # with group null, so the supervisor can chase it up.
        groupless = User.objects.create_user(
            email="groupless@example.com", first_name="Gro", last_name="Upless",
            password="pw12345!",
        )
        StudentProfile.objects.create(
            user=groupless, pg_first_name="P", pg_last_name="G",
            supervisor=profile, school_name="Test School", year_lvl="10",
        )

        url = reverse("grading:supervisor-grades")

        # Gate: nothing before marks are released.
        self.client.force_authenticate(supervisor)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

        self._release_now()
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        rows = {row["email"]: row for row in r.json()["students"]}
        self.assertEqual(set(rows), {"stud@example.com", "groupless@example.com"})

        in_group = rows["stud@example.com"]
        self.assertEqual(in_group["full_name"], "Sam Student")
        self.assertEqual(in_group["group"]["group_name"], "BTF-TEST-1")
        saq = next(c for c in in_group["components"] if c["code"] == "SAQ")
        self.assertEqual(saq["criteria"][0]["mark"], "8.00")

        no_group = rows["groupless@example.com"]
        self.assertIsNone(no_group["group"])
        self.assertEqual(no_group["components"], [])

    def test_supervisor_grades_listing_empty_for_non_supervisors(self):
        """A caller with no supervisor profile gets an empty roster, not an
        error — the guard in _supervised_students."""
        self._release_now()
        self.client.force_authenticate(self.non_staff)
        r = self.client.get(reverse("grading:supervisor-grades"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["students"], [])

    def test_excluded_finalist_cannot_download_certificate(self):
        _seed_doc_templates()
        self._release_certificates_now()
        rel = CertificatesRelease.load()
        rel.exclude_finalists = True
        rel.save()
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)

        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-certificate"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        # Dropping the exclusion (finalist flag intact) reopens the download.
        rel.exclude_finalists = False
        rel.save()
        r = self.client.get(reverse("grading:me-certificate"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
