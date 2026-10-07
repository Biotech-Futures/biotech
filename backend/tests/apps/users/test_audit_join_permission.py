import csv
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.users.models import StudentProfile, User


class AuditJoinPermissionCommandTests(TestCase):
    def _student(self, email, *, consented, response_id=None):
        user = User.objects.create_user(email=email, first_name="Kid", last_name=email.split("@")[0])
        StudentProfile.objects.create(
            user=user,
            pg_first_name="Pat",
            pg_last_name="Parent",
            parent_guardian_flag=True,
            school_name="Test High",
            year_lvl="10",
            has_join_permission=consented,
            joinperm_responseID=response_id,
            joinperm_granted_at=timezone.now() if consented else None,
        )
        return user

    def _run(self, *args):
        out = StringIO()
        call_command("audit_join_permission", *args, stdout=out)
        return out.getvalue()

    def setUp(self):
        self.verified = self._student("verified@test.com", consented=True, response_id="R_1")
        self.no_id = self._student("noid@test.com", consented=True, response_id=None)
        self.blank_id = self._student("blankid@test.com", consented=True, response_id="")
        self.pending = self._student("pending@test.com", consented=False)

    def test_summary_lists_only_consent_without_a_response(self):
        output = self._run()

        self.assertIn("with no consent response:      2", output)
        self.assertIn("noid@test.com", output)
        self.assertIn("blankid@test.com", output)
        self.assertNotIn("verified@test.com", output)
        self.assertNotIn("pending@test.com", output)

    def test_csv_output(self):
        rows = list(csv.reader(StringIO(self._run("--csv"))))

        self.assertEqual(rows[0][:2], ["user_id", "email"])
        self.assertEqual(
            sorted(row[1] for row in rows[1:]),
            ["blankid@test.com", "noid@test.com"],
        )

    def test_changes_nothing(self):
        self._run()
        self._run("--csv")

        self.assertEqual(StudentProfile.objects.filter(has_join_permission=True).count(), 3)

    def test_reports_a_clean_result(self):
        StudentProfile.objects.filter(user__in=[self.no_id, self.blank_id]).delete()

        self.assertIn("Every consented student has a consent response on record", self._run())
