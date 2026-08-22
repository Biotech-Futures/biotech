"""Tests for the team submission deadline rule and endpoints.

Focused on the places where a bug actually costs something: a team locked out
early, an entry accepted after closing, or someone reaching a team they are not
part of.
"""
from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import (
    Deadline,
    GroupExtension,
    Submission,
    SubmissionInstruction,
    SubmissionQuestion,
)
from apps.submissions.services import deadline_for_group
from apps.users.models import User


def _make_user(email, role_name, roles):
    user = User.objects.create_user(
        email=email, password="testUser@123", first_name="Test", last_name=role_name.title()
    )
    RoleAssignmentHistory.objects.create(
        user=user, role=roles[role_name], valid_from=timezone.now(), valid_to=None
    )
    return user


class DeadlineRuleTests(TestCase):
    """The rule itself, isolated from HTTP."""

    def setUp(self):
        self.group = Groups.objects.create(group_name="BTF-DEADLINE")

    def test_no_deadline_configured_is_closed(self):
        info = deadline_for_group(self.group.id)
        self.assertIsNone(info.closes_at)
        self.assertFalse(info.is_open)

    def test_inactive_deadline_is_ignored(self):
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=False)
        self.assertFalse(deadline_for_group(self.group.id).is_open)

    def test_active_deadline_in_future_is_open(self):
        closes = timezone.now() + timedelta(days=1)
        Deadline.objects.create(closes_at=closes, is_active=True)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, closes)
        self.assertFalse(info.is_extended)
        self.assertTrue(info.is_open)

    def test_past_deadline_is_closed(self):
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=1), is_active=True)
        self.assertFalse(deadline_for_group(self.group.id).is_open)

    def test_extension_reopens_a_passed_deadline(self):
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=1), is_active=True)
        extended = timezone.now() + timedelta(days=2)
        GroupExtension.objects.create(group=self.group, extended_until=extended)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, extended)
        self.assertTrue(info.is_extended)
        self.assertTrue(info.is_open)

    def test_extension_applies_only_to_its_own_group(self):
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=1), is_active=True)
        GroupExtension.objects.create(
            group=self.group, extended_until=timezone.now() + timedelta(days=2)
        )
        other = Groups.objects.create(group_name="BTF-OTHER")

        self.assertTrue(deadline_for_group(self.group.id).is_open)
        self.assertFalse(deadline_for_group(other.id).is_open)

    def test_grace_period_keeps_submissions_open_past_the_announced_date(self):
        # The announced date has passed but the buffer has not: still open, and
        # flagged as being inside the grace window.
        Deadline.objects.create(
            closes_at=timezone.now() - timedelta(hours=2), grace_hours=24, is_active=True
        )

        info = deadline_for_group(self.group.id)
        self.assertTrue(info.is_open)
        self.assertTrue(info.is_in_grace)

    def test_submissions_close_once_the_grace_period_ends(self):
        Deadline.objects.create(
            closes_at=timezone.now() - timedelta(hours=30), grace_hours=24, is_active=True
        )

        info = deadline_for_group(self.group.id)
        self.assertFalse(info.is_open)
        self.assertFalse(info.is_in_grace)

    def test_students_are_shown_the_announced_date_not_the_buffer(self):
        # The whole point of the buffer is that it is not published — students
        # see one date and the server quietly accepts a little longer.
        closes = timezone.now() + timedelta(days=1)
        Deadline.objects.create(closes_at=closes, grace_hours=24, is_active=True)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, closes)
        self.assertEqual(info.enforced_until, closes + timedelta(hours=24))

    def test_an_extension_gets_no_extra_grace(self):
        # A granted date is explicit, unlike an announced one, so it applies
        # exactly as the admin entered it.
        Deadline.objects.create(
            closes_at=timezone.now() - timedelta(days=2), grace_hours=24, is_active=True
        )
        extended = timezone.now() + timedelta(days=1)
        GroupExtension.objects.create(group=self.group, extended_until=extended)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, extended)
        self.assertEqual(info.enforced_until, extended)

    def test_extension_is_applied_exactly_as_entered(self):
        # An extension earlier than the standard deadline shortens the window
        # rather than being quietly corrected upwards. Documents the deliberate
        # choice made in services.deadline_for_group.
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=5), is_active=True)
        GroupExtension.objects.create(
            group=self.group, extended_until=timezone.now() - timedelta(hours=1)
        )
        self.assertFalse(deadline_for_group(self.group.id).is_open)


class SubmissionApiTests(TestCase):
    def setUp(self):
        self.roles = {
            name: Roles.objects.create(role_name=name)
            for name in ("student", "mentor", "supervisor")
        }
        self.group = Groups.objects.create(group_name="BTF-API")

        self.student = _make_user("student@test.local", "student", self.roles)
        self.mentor = _make_user("mentor@test.local", "mentor", self.roles)
        self.outsider = _make_user("outsider@test.local", "student", self.roles)

        for user, role in ((self.student, "student"), (self.mentor, "mentor")):
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)

        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})

    def _client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _answer_everything(self):
        """Fill every required question, so submit is testing what it claims."""
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {
            question.key: "An answer."
            for question in SubmissionQuestion.active().filter(is_required=True)
        }
        submission.save(update_fields=["answers"])

    def _attach_poster(self):
        """Satisfy the "a poster is required to submit" rule.

        Written straight onto the record rather than uploaded, so these tests
        stay about deadlines and permissions; real uploads are covered in
        test_submission_files.py.
        """
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.poster = {
            "storage_key": "test/poster.pdf",
            "name": "poster.pdf",
            "mime": "application/pdf",
            "size": 1024,
        }
        submission.save(update_fields=["poster"])

    # ---------------------------------------------------------------- reading
    def test_member_reads_empty_submission(self):
        response = self._client_for(self.student).get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["submission"])
        self.assertTrue(response.data["deadline"]["is_open"])
        self.assertEqual(response.data["group"]["name"], "BTF-API")

    def test_non_member_is_refused(self):
        response = self._client_for(self.outsider).get(self.detail_url)
        self.assertEqual(response.status_code, 403)

    def test_mentor_may_not_read(self):
        # Mentors guide the group's work but have no part in assessment, so a
        # team's entry is not theirs to see — even though they are members.
        response = self._client_for(self.mentor).get(self.detail_url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "student_role_required")

    # ---------------------------------------------------------------- writing
    def test_student_saves_a_draft(self):
        response = self._client_for(self.student).put(
            self.detail_url,
            {"answers": {"q1": "Our project"}, "prototype_url": "https://example.com/demo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        submission = Submission.objects.get(group=self.group)
        self.assertEqual(submission.answers, {"q1": "Our project"})
        self.assertEqual(submission.prototype_url, "https://example.com/demo")
        # Saving a draft must not look like submitting.
        self.assertIsNone(submission.submitted_at)

    def test_partial_save_keeps_untouched_fields(self):
        client = self._client_for(self.student)
        client.put(self.detail_url, {"answers": {"q1": "Kept"}}, format="json")
        client.put(
            self.detail_url, {"prototype_url": "https://example.com/x"}, format="json"
        )

        submission = Submission.objects.get(group=self.group)
        self.assertEqual(submission.answers, {"q1": "Kept"})

    def test_mentor_may_not_write(self):
        response = self._client_for(self.mentor).put(
            self.detail_url, {"answers": {"q1": "x"}}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_non_member_may_not_write(self):
        response = self._client_for(self.outsider).put(
            self.detail_url, {"answers": {"q1": "x"}}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    # ------------------------------------------------------------- submitting
    def test_submitting_without_a_poster_is_refused(self):
        client = self._client_for(self.student)
        client.put(self.detail_url, {"answers": {"q1": "Done"}}, format="json")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Submission.objects.get(group=self.group).submitted_at)

    def test_submitting_with_a_required_question_blank_is_refused(self):
        client = self._client_for(self.student)
        self._attach_poster()
        # q1 answered, the other required questions left blank.
        client.put(self.detail_url, {"answers": {"q1": "Only this one"}}, format="json")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data.get("missing"))
        self.assertIsNone(Submission.objects.get(group=self.group).submitted_at)

    def test_student_submits(self):
        client = self._client_for(self.student)
        self._attach_poster()
        self._answer_everything()
        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        submission = Submission.objects.get(group=self.group)
        self.assertIsNotNone(submission.submitted_at)
        self.assertEqual(submission.submitted_by, self.student)
        self.assertFalse(submission.is_late)

    def test_resubmitting_updates_the_same_row(self):
        client = self._client_for(self.student)
        self._attach_poster()
        self._answer_everything()

        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)
        answers = {q.key: "Revised" for q in SubmissionQuestion.active()}
        client.put(self.detail_url, {"answers": answers}, format="json")
        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)

        self.assertEqual(Submission.objects.filter(group=self.group).count(), 1)
        self.assertEqual(Submission.objects.get(group=self.group).answers, answers)

    # ---------------------------------------------------------------- questions
    def test_questions_are_returned_in_order(self):
        response = self._client_for(self.student).get(self.detail_url)

        keys = [question["key"] for question in response.data["questions"]]
        self.assertEqual(keys, ["q1", "q2", "q3", "q4"])

    def test_upload_limits_are_published_per_slot(self):
        # The page states each limit and refuses oversized files before
        # uploading, so they have to come from the server rather than hardcoded
        # copies that could drift out of step with the settings.
        response = self._client_for(self.student).get(self.detail_url)
        limits = response.data["max_file_sizes"]

        self.assertEqual(limits["poster"], settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE)
        self.assertEqual(limits["report"], settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE)
        self.assertEqual(limits["prototype"], settings.SUBMISSION_FILE_MAX_UPLOAD_SIZE)
        # The whole point of splitting them: a prototype may be far larger.
        self.assertGreater(limits["prototype"], limits["poster"])

    def test_instructions_are_returned_per_section(self):
        # Guidance is editable by admins, so the page renders what the server
        # sends rather than anything built into it.
        response = self._client_for(self.student).get(self.detail_url)
        instructions = response.data["instructions"]

        self.assertEqual(set(instructions), {"questions", "poster", "extras"})
        self.assertTrue(all(body.strip() for body in instructions.values()))

    def test_edited_instructions_are_served(self):
        SubmissionInstruction.objects.filter(section="poster").update(body="New wording.")

        response = self._client_for(self.student).get(self.detail_url)

        self.assertEqual(response.data["instructions"]["poster"], "New wording.")

    def test_retired_questions_are_hidden(self):
        SubmissionQuestion.objects.filter(key="q4").update(is_active=False)

        response = self._client_for(self.student).get(self.detail_url)

        keys = [question["key"] for question in response.data["questions"]]
        self.assertEqual(keys, ["q1", "q2", "q3"])

    def test_unknown_answer_key_is_rejected(self):
        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {"nope": "x"}}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_answer_longer_than_the_limit_is_rejected(self):
        SubmissionQuestion.objects.filter(key="q1").update(max_length=10)

        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {"q1": "x" * 11}}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    # ---------------------------------------------------------------- closing
    def test_writes_refused_after_deadline(self):
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))
        client = self._client_for(self.student)

        self.assertEqual(
            client.put(self.detail_url, {"answers": {"q1": "late"}}, format="json").status_code,
            403,
        )
        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 403)

    def test_reading_still_works_after_deadline(self):
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))
        response = self._client_for(self.student).get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["deadline"]["is_open"])

    def test_extension_lets_one_team_keep_writing(self):
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))
        GroupExtension.objects.create(
            group=self.group, extended_until=timezone.now() + timedelta(days=1)
        )

        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {"q1": "extended"}}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["deadline"]["is_extended"])

    def test_writes_refused_when_no_deadline_configured(self):
        Deadline.objects.all().delete()
        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {"q1": "x"}}, format="json"
        )
        self.assertEqual(response.status_code, 403)
