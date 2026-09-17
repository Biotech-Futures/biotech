"""Tests for the submission deadline rule and endpoints."""
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

from .seed_data import install_instructions, install_question_set


def _make_user(email, role_name, roles):
    user = User.objects.create_user(
        email=email, password="testUser@123", first_name="Test", last_name=role_name.title()
    )
    RoleAssignmentHistory.objects.create(
        user=user, role=roles[role_name], valid_from=timezone.now(), valid_to=None
    )
    return user


class DeadlineRuleTests(TestCase):
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
        closes = timezone.now() + timedelta(days=1)
        Deadline.objects.create(closes_at=closes, grace_hours=24, is_active=True)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, closes)
        self.assertEqual(info.enforced_until, closes + timedelta(hours=24))

    def test_an_extension_does_not_inherit_the_global_grace(self):
        Deadline.objects.create(
            closes_at=timezone.now() - timedelta(days=2), grace_hours=24, is_active=True
        )
        extended = timezone.now() + timedelta(days=1)
        GroupExtension.objects.create(group=self.group, extended_until=extended)

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, extended)
        self.assertEqual(info.enforced_until, extended)

    def test_an_extension_grace_keeps_submissions_open_past_the_granted_date(self):
        extended = timezone.now() - timedelta(hours=2)
        GroupExtension.objects.create(
            group=self.group, extended_until=extended, grace_hours=24
        )

        info = deadline_for_group(self.group.id)
        self.assertEqual(info.closes_at, extended)
        self.assertEqual(info.enforced_until, extended + timedelta(hours=24))
        self.assertTrue(info.is_open)
        self.assertTrue(info.is_in_grace)

    def test_extension_is_applied_exactly_as_entered(self):
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
        self.supervisor = _make_user("supervisor@test.local", "supervisor", self.roles)
        self.outsider = _make_user("outsider@test.local", "student", self.roles)

        for user, role in (
            (self.student, "student"), (self.mentor, "mentor"), (self.supervisor, "supervisor"),
        ):
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)

        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})

        self.question_keys = [q.key for q in install_question_set()]
        install_instructions()
        self.first_key = self.question_keys[0]

    def _client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _answer_everything(self):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {
            question.key: "An answer."
            for question in SubmissionQuestion.active().filter(is_required=True)
        }
        submission.save(update_fields=["answers"])

    def _attach_poster(self):
        """Record a poster directly; real uploads are covered in test_submission_files."""
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.poster = {
            "storage_key": "test/poster.pdf",
            "name": "poster.pdf",
            "mime": "application/pdf",
            "size": 1024,
        }
        submission.save(update_fields=["poster"])

    def test_member_reads_empty_submission(self):
        response = self._client_for(self.student).get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["submission"])
        self.assertTrue(response.data["deadline"]["is_open"])
        self.assertEqual(response.data["group"]["name"], "BTF-API")

    def test_non_member_is_refused(self):
        response = self._client_for(self.outsider).get(self.detail_url)
        self.assertEqual(response.status_code, 403)

    def test_mentor_and_supervisor_on_the_team_may_read(self):
        for member in (self.mentor, self.supervisor):
            with self.subTest(member=member.email):
                response = self._client_for(member).get(self.detail_url)
                self.assertEqual(response.status_code, 200)

    def test_mentor_not_on_the_team_is_refused(self):
        other = Groups.objects.create(group_name="BTF-ELSEWHERE")
        url = reverse("group-submission", kwargs={"group_id": other.id})

        self.assertEqual(self._client_for(self.mentor).get(url).status_code, 403)

    def test_student_saves_a_draft(self):
        response = self._client_for(self.student).put(
            self.detail_url,
            {"answers": {self.first_key: "Our project"}, "prototype_url": "https://example.com/demo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        submission = Submission.objects.get(group=self.group)
        self.assertEqual(submission.answers, {self.first_key: "Our project"})
        self.assertEqual(submission.prototype_url, "https://example.com/demo")
        self.assertIsNone(submission.submitted_at)

    def test_partial_save_keeps_untouched_fields(self):
        client = self._client_for(self.student)
        client.put(self.detail_url, {"answers": {self.first_key: "Kept"}}, format="json")
        client.put(
            self.detail_url, {"prototype_url": "https://example.com/x"}, format="json"
        )

        submission = Submission.objects.get(group=self.group)
        self.assertEqual(submission.answers, {self.first_key: "Kept"})

    def test_mentor_and_supervisor_on_the_team_may_write(self):
        for member in (self.mentor, self.supervisor):
            with self.subTest(member=member.email):
                response = self._client_for(member).put(
                    self.detail_url, {"answers": {self.first_key: member.email}}, format="json"
                )
                self.assertEqual(response.status_code, 200)

    def test_supervisor_on_the_team_may_submit(self):
        self._answer_everything()
        self._attach_poster()

        response = self._client_for(self.supervisor).post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.objects.get(group=self.group).submitted_by, self.supervisor)

    def test_non_member_may_not_write(self):
        response = self._client_for(self.outsider).put(
            self.detail_url, {"answers": {self.first_key: "x"}}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_submitting_without_a_poster_is_refused(self):
        client = self._client_for(self.student)
        client.put(self.detail_url, {"answers": {self.first_key: "Done"}}, format="json")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Submission.objects.get(group=self.group).submitted_at)

    def test_submitting_with_a_required_question_blank_is_refused(self):
        client = self._client_for(self.student)
        self._attach_poster()
        client.put(self.detail_url, {"answers": {self.first_key: "Only this one"}}, format="json")

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
        reopen_url = reverse("group-submission-reopen", kwargs={"group_id": self.group.id})
        self._attach_poster()
        self._answer_everything()

        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)
        self.assertEqual(client.post(reopen_url, {}, format="json").status_code, 200)

        answers = {q.key: "Revised" for q in SubmissionQuestion.active()}
        client.put(self.detail_url, {"answers": answers}, format="json")
        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)

        self.assertEqual(Submission.objects.filter(group=self.group).count(), 1)
        self.assertEqual(Submission.objects.get(group=self.group).submitted_answers, answers)

    def test_questions_are_returned_in_order(self):
        response = self._client_for(self.student).get(self.detail_url)

        keys = [question["key"] for question in response.data["questions"]]
        self.assertEqual(keys, self.question_keys)

    def test_upload_limits_are_published_per_slot(self):
        response = self._client_for(self.student).get(self.detail_url)
        limits = response.data["max_file_sizes"]

        self.assertEqual(limits["poster"], settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE)
        self.assertEqual(limits["report"], settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE)
        self.assertEqual(limits["prototype"], settings.SUBMISSION_FILE_MAX_UPLOAD_SIZE)
        self.assertGreater(limits["prototype"], limits["poster"])

    def test_instructions_are_returned_per_section(self):
        response = self._client_for(self.student).get(self.detail_url)
        instructions = response.data["instructions"]

        self.assertEqual(set(instructions), {"questions", "poster", "extras"})
        for section in instructions.values():
            self.assertTrue(section["heading"].strip())
            self.assertTrue(section["body"].strip())

    def test_edited_instructions_are_served(self):
        SubmissionInstruction.objects.filter(section="poster").update(
            heading="Your poster", body="New wording."
        )

        response = self._client_for(self.student).get(self.detail_url)

        self.assertEqual(
            response.data["instructions"]["poster"],
            {"heading": "Your poster", "body": "New wording."},
        )

    def test_a_write_after_the_deadline_is_refused(self):
        Deadline.objects.all().update(closes_at=timezone.now() - timedelta(hours=1))

        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {self.first_key: "Too late."}}, format="json"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "submissions_closed")

    def test_a_submit_after_the_deadline_is_refused_the_same_way(self):
        Deadline.objects.all().update(closes_at=timezone.now() - timedelta(hours=1))

        response = self._client_for(self.student).post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "submissions_closed")

    def test_retired_questions_are_hidden(self):
        SubmissionQuestion.objects.filter(key=self.question_keys[-1]).update(is_active=False)

        response = self._client_for(self.student).get(self.detail_url)

        keys = [question["key"] for question in response.data["questions"]]
        self.assertEqual(keys, self.question_keys[:-1])

    def test_unknown_answer_key_is_rejected(self):
        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {"nope": "x"}}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_answer_over_the_word_limit_is_rejected(self):
        key = SubmissionQuestion.active().first().key
        SubmissionQuestion.objects.filter(key=key).update(max_words=5)
        client = self._client_for(self.student)

        over = client.put(self.detail_url, {"answers": {key: "one two three four five six"}}, format="json")
        exactly = client.put(self.detail_url, {"answers": {key: "one two three four five"}}, format="json")

        self.assertEqual(over.status_code, 400)
        self.assertEqual(exactly.status_code, 200)

    def test_the_over_limit_message_names_the_question_not_its_key(self):
        question = SubmissionQuestion.active().first()
        question.max_words = 5
        question.save()

        response = self._client_for(self.student).put(
            self.detail_url,
            {"answers": {question.key: "one two three four five six"}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        body = str(response.data)
        self.assertIn(question.prompt, body)
        self.assertNotIn(question.key, body)

    def test_word_count_ignores_extra_whitespace(self):
        key = SubmissionQuestion.active().first().key
        SubmissionQuestion.objects.filter(key=key).update(max_words=3)

        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {key: "  one \n\n two    three  "}}, format="json"
        )

        self.assertEqual(response.status_code, 200)

    def test_writes_refused_after_deadline(self):
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))
        client = self._client_for(self.student)

        self.assertEqual(
            client.put(self.detail_url, {"answers": {self.first_key: "late"}}, format="json").status_code,
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
            self.detail_url, {"answers": {self.first_key: "extended"}}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["deadline"]["is_extended"])

    def test_writes_refused_when_no_deadline_configured(self):
        Deadline.objects.all().delete()
        response = self._client_for(self.student).put(
            self.detail_url, {"answers": {self.first_key: "x"}}, format="json"
        )
        self.assertEqual(response.status_code, 403)
