"""Tests for grading's content adapter (services.content).

The adapter is the single seam between grading and the student portal's
slot-based Submission row: it must expose only submitted snapshots, expand one
row into per-component entries, and reproduce the marking payload shape.
"""
from importlib import import_module

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.common.storage import reset_managed_storage_caches
from apps.grading.models import ComponentFeedback, SubmissionComponent
from apps.grading.services import content
from apps.groups.models import Groups
from apps.submissions.models import Submission, SubmissionQuestion
from apps.users.models import User


def install_components():
    """Mirror the grading 0002 seed — settings_test disables migrations."""
    seed = import_module("apps.grading.migrations.0002_seed_components").COMPONENTS
    return {
        row["code"]: SubmissionComponent.objects.create(**row)
        for row in seed
    }


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class ContentAdapterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.components = install_components()
        cls.group = Groups.objects.create(group_name="BTF-ADAPT")
        cls.other_group = Groups.objects.create(group_name="BTF-OTHER")
        cls.user = User.objects.create_user(
            email="adapter@test.local", password="testUser@123",
            first_name="Ada", last_name="Pter",
        )
        SubmissionQuestion.objects.create(
            key="q_purpose", prompt="What does your solution do?", order=10,
        )
        SubmissionQuestion.objects.create(
            key="q_how", prompt="How does it work?", order=20,
        )

    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

    def _submitted(self, group=None, **overrides) -> Submission:
        submission = Submission.objects.create(
            group=group or self.group,
            answers={"q_purpose": "It measures lead.", "q_how": "GFP reporter."},
            poster={"storage_key": "2026/01/01/x/poster.pdf", "name": "poster.pdf",
                    "mime": "application/pdf", "size": 123},
        )
        for field, value in overrides.items():
            setattr(submission, field, value)
        submission.snapshot(self.user)
        submission.save()
        return submission

    # ------------------------------------------------------------ visibility
    def test_draft_only_submission_is_invisible(self):
        Submission.objects.create(group=self.group, answers={"q_purpose": "draft"})
        self.assertEqual(content.submission_entries(), [])

    def test_submitted_entry_expands_into_components(self):
        submission = self._submitted()
        entries = content.submission_entries(group_id=self.group.id)
        codes = sorted(e.component_code for e in entries)
        self.assertEqual(codes, ["POSTER", "SAQ"])  # no report/prototype attached
        for entry in entries:
            self.assertEqual(entry.submission_id, submission.id)
            self.assertEqual(entry.group_id, self.group.id)
            self.assertEqual(entry.group_name, "BTF-ADAPT")
            self.assertEqual(entry.submitted_at, submission.submitted_at)

    def test_reads_snapshot_not_draft(self):
        submission = self._submitted()
        # Reopen and mutate the draft: markers must keep seeing the snapshot.
        submission.reopened_at = timezone.now()
        submission.answers = {"q_purpose": "totally rewritten"}
        submission.poster = None
        submission.save()

        entries = content.submission_entries(group_id=self.group.id)
        saq = next(e for e in entries if e.component_code == "SAQ")
        self.assertIn("It measures lead.", saq.text)
        self.assertNotIn("totally rewritten", saq.text)
        self.assertTrue(any(e.component_code == "POSTER" for e in entries))

    def test_link_only_prototype_appears(self):
        self._submitted(prototype_url="https://example.com/demo")
        entries = content.submission_entries(
            group_id=self.group.id, component_code="PROTOTYPE"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].link, "https://example.com/demo")
        self.assertIsNone(entries[0].file)

    def test_component_filter_and_group_ids(self):
        self._submitted()
        self._submitted(group=self.other_group)
        only_poster = content.submission_entries(component_code="POSTER")
        self.assertEqual(len(only_poster), 2)
        scoped = content.submission_entries(
            component_code="POSTER", group_ids=[self.other_group.id]
        )
        self.assertEqual([e.group_id for e in scoped], [self.other_group.id])

    # ---------------------------------------------------------------- shapes
    def test_saq_text_carries_question_prompts(self):
        self._submitted()
        saq = content.submission_entries(
            group_id=self.group.id, component_code="SAQ"
        )[0]
        self.assertIn("What does your solution do?", saq.text)
        self.assertIn("It measures lead.", saq.text)
        # Question order respected.
        self.assertLess(
            saq.text.index("What does your solution do?"),
            saq.text.index("How does it work?"),
        )

    def test_entry_payload_matches_marking_contract(self):
        submission = self._submitted()
        poster = content.submission_entries(
            group_id=self.group.id, component_code="POSTER"
        )[0]
        payload = content.entry_payload(poster, overall_comment="Nice work")
        self.assertEqual(payload["id"], submission.id)
        self.assertEqual(payload["component"], self.components["POSTER"].id)
        self.assertEqual(payload["is_late"], False)
        self.assertEqual(payload["overall_comment"], "Nice work")
        self.assertEqual(payload["file_name"], "poster.pdf")
        # Local storage still yields a URL; a missing blob would yield None
        # rather than raising.
        self.assertTrue(payload["file_url"] is None or "poster.pdf" in payload["file_url"])
        self.assertIsNone(content.entry_payload(None))

    def test_entries_by_submission_groups_shared_id(self):
        submission = self._submitted()
        grouped = content.entries_by_submission(
            content.submission_entries(group_id=self.group.id)
        )
        self.assertEqual(set(grouped), {submission.id})
        self.assertEqual(len(grouped[submission.id]), 2)

    def test_feedback_map(self):
        ComponentFeedback.objects.create(
            group=self.group, component=self.components["POSTER"], comment="Strong",
        )
        fmap = content.feedback_map([self.group.id])
        self.assertEqual(
            fmap[(self.group.id, self.components["POSTER"].id)], "Strong"
        )
        self.assertEqual(content.feedback_map([self.other_group.id]), {})
