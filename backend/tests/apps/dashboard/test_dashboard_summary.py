from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Events
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.matching_runtime.models import MatchRecommendation, MatchRun
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope, MentorProfile


User = get_user_model()


class DashboardSummaryApiTests(TestCase):
    """End-to-end tests for ``GET /dashboard/summary/`` (DashboardViewSet.summary)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("dashboard-summary")

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)
        self.other_track = Tracks.objects.create(track_name="AUS-VIC", state=self.state)

    # ----- Auth ---------------------------------------------------------

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ----- Shape --------------------------------------------------------

    def test_response_shape_is_user_stats_admin(self):
        user = User.objects.create_user(
            email="shape@test.com", password="pass", first_name="Sh", last_name="Ape",
            track=self.track,
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {"user", "stats", "admin"})
        self.assertEqual(
            set(response.data["stats"].keys()),
            {"my_groups", "upcoming_events", "resources", "announcements",
             "tasks_completed", "tasks_total"},
        )
        self.assertIsNone(response.data["admin"])

    # ----- Student counts ----------------------------------------------

    def test_student_my_groups_counts_active_memberships_only(self):
        student = User.objects.create_user(
            email="stu@test.com", password="pass", first_name="St", last_name="U",
            track=self.track,
        )
        group_a = Groups.objects.create(group_name="A", track=self.track)
        group_b = Groups.objects.create(group_name="B", track=self.track)
        left_group = Groups.objects.create(group_name="Left", track=self.track)
        GroupMembership.objects.create(group=group_a, user=student, membership_role="student")
        GroupMembership.objects.create(group=group_b, user=student, membership_role="student")
        now = timezone.now()
        GroupMembership.objects.create(
            group=left_group, user=student, membership_role="student",
            joined_at=now - timedelta(days=1), left_at=now,
        )

        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        self.assertEqual(response.data["stats"]["my_groups"], 2)

    def test_task_counts_match_progress_snapshot(self):
        student = User.objects.create_user(
            email="stu_tasks@test.com", password="pass", first_name="T", last_name="K",
            track=self.track,
        )
        group = Groups.objects.create(group_name="TaskGroup", track=self.track)
        GroupMembership.objects.create(group=group, user=student, membership_role="student")

        common = dict(
            task_type=TaskType.GROUP, group=group,
            due_date=timezone.now() + timedelta(days=7),
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        Task.objects.create(name="t1", completed=True, **common)
        Task.objects.create(name="t2", completed=True, **common)
        Task.objects.create(name="t3", completed=False, **common)

        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        self.assertEqual(response.data["stats"]["tasks_completed"], 2)
        self.assertEqual(response.data["stats"]["tasks_total"], 3)

    def test_upcoming_events_excludes_past_and_deleted(self):
        student = User.objects.create_user(
            email="stu_ev@test.com", password="pass", first_name="E", last_name="V",
            track=self.track,
        )
        now = timezone.now()
        # Untargeted (platform-wide) future event — visible to everyone.
        Events.objects.create(
            event_name="Future Open",
            start_datetime=now + timedelta(days=1),
            ends_datetime=now + timedelta(days=1, hours=1),
            is_virtual=True,
        )
        Events.objects.create(
            event_name="Past",
            start_datetime=now - timedelta(days=2),
            ends_datetime=now - timedelta(days=2) + timedelta(hours=1),
            is_virtual=True,
        )
        Events.objects.create(
            event_name="Deleted",
            start_datetime=now + timedelta(days=3),
            ends_datetime=now + timedelta(days=3, hours=1),
            is_virtual=True,
            deleted_at=now,
        )

        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        self.assertEqual(response.data["stats"]["upcoming_events"], 1)

    # ----- Mentor scoping ----------------------------------------------

    def test_mentor_my_groups_counts_mentor_memberships_only(self):
        mentor = User.objects.create_user(
            email="men@test.com", password="pass", first_name="Me", last_name="N",
            track=self.track,
        )
        MentorProfile.objects.create(
            user=mentor, institution="Uni", mentor_reason="help",
        )
        mentor_group = Groups.objects.create(group_name="MGroup", track=self.track)
        GroupMembership.objects.create(group=mentor_group, user=mentor, membership_role="mentor")

        # Same user as student in an unrelated group — `mine=True` counts both.
        student_group = Groups.objects.create(group_name="SGroup", track=self.track)
        GroupMembership.objects.create(group=student_group, user=mentor, membership_role="student")

        self.client.force_authenticate(user=mentor)
        response = self.client.get(self.url)
        self.assertEqual(response.data["stats"]["my_groups"], 2)

    # ----- Admin section -----------------------------------------------

    def test_non_admin_has_null_admin_section(self):
        student = User.objects.create_user(
            email="na@test.com", password="pass", first_name="N", last_name="A",
            track=self.track,
        )
        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        self.assertIsNone(response.data["admin"])

    def test_track_scoped_admin_only_sees_in_scope_counts(self):
        admin = User.objects.create_user(
            email="ta@test.com", password="pass", first_name="T", last_name="A",
        )
        AdminScope.objects.create(user=admin, track=self.track, is_global=False)

        Groups.objects.create(group_name="InScope", track=self.track)
        Groups.objects.create(group_name="OutOfScope", track=self.other_track)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        admin_payload = response.data["admin"]
        self.assertIsNotNone(admin_payload)
        self.assertEqual(admin_payload["active_groups"], 1)
        self.assertEqual(admin_payload["track_scope"], [self.track.id])

    def test_global_admin_sees_all_tracks_in_admin_section(self):
        admin = User.objects.create_user(
            email="ga@test.com", password="pass", first_name="G", last_name="A",
            is_staff=True,
        )
        Groups.objects.create(group_name="A", track=self.track)
        Groups.objects.create(group_name="B", track=self.other_track)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        admin_payload = response.data["admin"]
        self.assertIsNotNone(admin_payload)
        self.assertEqual(admin_payload["active_groups"], 2)
        # Global admins have a null/empty track scope serialized as [].
        self.assertEqual(admin_payload["track_scope"], [])

    def test_pending_matches_only_counts_groups_still_needing_a_mentor(self):
        """Gap #3 — MatchRecommendation has no declined/expired state, so we
        proxy 'actionable' by 'group still lacks an active mentor'."""
        admin = User.objects.create_user(
            email="pm@test.com", password="pass", first_name="P", last_name="M",
            is_staff=True,
        )
        # Recommendation #1: group has NO mentor → actionable.
        mentorless = Groups.objects.create(group_name="NoMentor", track=self.track)
        # Recommendation #2: group already has an active mentor → not actionable.
        mentored = Groups.objects.create(group_name="HasMentor", track=self.track)
        sitting_mentor = User.objects.create_user(
            email="sm@test.com", password="pass", first_name="S", last_name="M",
        )
        GroupMembership.objects.create(group=mentored, user=sitting_mentor, membership_role="mentor")

        run = MatchRun.objects.create(initiated_by_user=admin, track=self.track, run_type="initial")
        MatchRecommendation.objects.create(match_run=run, group=mentorless, mentor_user=sitting_mentor)
        MatchRecommendation.objects.create(match_run=run, group=mentored, mentor_user=sitting_mentor)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        self.assertEqual(response.data["admin"]["unassigned_match_recommendations"], 1)
        self.assertEqual(response.data["admin"]["groups_without_mentor"], 1)
