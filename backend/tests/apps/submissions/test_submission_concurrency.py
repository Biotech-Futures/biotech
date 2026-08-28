"""Tests for two teammates editing one entry at the same time.

A submission is a shared document: several students on a team can have the
portal open at once, and auto-save fires without anyone pressing anything. The
behaviour that matters is that work on *different* questions never collides,
because that is what teams actually do — they split the questions up.

Editing the *same* question is still last-write-wins. That is a deliberate
accepted limit rather than an oversight: the team can see and resubmit.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class ConcurrentEditTests(TestCase):
    def setUp(self):
        self.role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-CONCURRENT")
        self.ada = self._student("ada@test.local")
        self.grace = self._student("grace@test.local")
        self.questions = install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)
        self.url = reverse("group-submission", kwargs={"group_id": self.group.id})

    def _student(self, email):
        user = User.objects.create_user(
            email=email, password="testUser@123", first_name="Test", last_name="Student"
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=self.role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=user, membership_role="student"
        )
        return user

    def _client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _save(self, user, answers):
        return self._client_for(user).put(self.url, {"answers": answers}, format="json")

    def _stored(self):
        return Submission.objects.get(group=self.group).answers

    # ------------------------------------------------------------- the fix
    def test_teammates_on_different_questions_do_not_overwrite_each_other(self):
        first, second = self.questions[0].key, self.questions[1].key

        self.assertEqual(self._save(self.ada, {first: "Ada's answer."}).status_code, 200)
        self.assertEqual(self._save(self.grace, {second: "Grace's answer."}).status_code, 200)

        stored = self._stored()
        self.assertEqual(stored[first], "Ada's answer.")
        self.assertEqual(stored[second], "Grace's answer.")

    def test_a_save_leaves_untouched_answers_alone(self):
        first, second = self.questions[0].key, self.questions[1].key
        self._save(self.ada, {first: "Kept.", second: "Also kept."})

        # A later save mentioning only one question must not clear the other.
        self._save(self.ada, {first: "Edited."})

        stored = self._stored()
        self.assertEqual(stored[first], "Edited.")
        self.assertEqual(stored[second], "Also kept.")

    # -------------------------------------------------- the accepted limits
    def test_clearing_an_answer_requires_an_explicit_empty_string(self):
        # The consequence of merging: omitting a key means "leave it alone", so
        # an emptied box has to be sent as "". The page does this naturally.
        key = self.questions[0].key
        self._save(self.ada, {key: "Written."})

        self._save(self.ada, {key: ""})

        self.assertEqual(self._stored()[key], "")

    def test_the_same_question_is_still_last_write_wins(self):
        # Documents the limit accepted when choosing per-question saves over a
        # version guard: two people editing one question still resolve by
        # whoever saved last.
        key = self.questions[0].key

        self._save(self.ada, {key: "Ada's version."})
        self._save(self.grace, {key: "Grace's version."})

        self.assertEqual(self._stored()[key], "Grace's version.")

    def test_an_empty_answers_payload_changes_nothing(self):
        # The page sends only what changed, so a save with nothing to report is
        # normal rather than an error.
        key = self.questions[0].key
        self._save(self.ada, {key: "Untouched."})

        self.assertEqual(self._save(self.grace, {}).status_code, 200)
        self.assertEqual(self._stored()[key], "Untouched.")
