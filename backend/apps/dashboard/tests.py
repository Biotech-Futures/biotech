from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import EventRsvp, EventTargetGroup, Events
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.tasks.models import Milestone, Tasks

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixture helper
# ---------------------------------------------------------------------------

class DashboardFixtureMixin:
    """Creates a reusable set of users, groups, milestones, and tasks."""

    def _create_fixtures(self):
        self.user = User.objects.create_user(
            email="student@dash.test",
            password="pass",
            first_name="Alice",
            last_name="Student",
        )
        self.admin = User.objects.create_user(
            email="admin@dash.test",
            password="pass",
            first_name="Admin",
            last_name="User",
            is_staff=True,
        )

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.user.track = self.track
        self.user.save(update_fields=["track"])

        self.group = Groups.objects.create(group_name="Dash Group", track=self.track)
        self.membership = GroupMembership.objects.create(
            group=self.group, user=self.user, membership_role="member"
        )

        self.milestone = Milestone.objects.create(
            group=self.group,
            milestone_name="Week 1",
            sort_order=10,
            due_date=timezone.now() + timezone.timedelta(days=7),
            start_date=timezone.now(),
        )
        self.milestone2 = Milestone.objects.create(
            group=self.group,
            milestone_name="Week 2",
            sort_order=20,
            due_date=timezone.now() + timezone.timedelta(days=14),
        )

        # status is now the single source of truth — no completed field
        self.task_todo = Tasks.objects.create(
            task_name="Task A",
            due_date=timezone.now() + timezone.timedelta(days=3),
            milestone=self.milestone,
            status=Tasks.Status.TODO,
        )
        self.task_done = Tasks.objects.create(
            task_name="Task B",
            due_date=timezone.now() + timezone.timedelta(days=4),
            milestone=self.milestone,
            status=Tasks.Status.DONE,
        )


# ---------------------------------------------------------------------------
# #1 – GET /dashboard/v1/progress/
# ---------------------------------------------------------------------------

class ProgressSnapshotTests(DashboardFixtureMixin, APITestCase):
    """
    Tests for the new Progress Snapshot endpoint.

    Covers authentication, group derivation, completion rate calculation
    (using status==done as the completion signal), next_milestone population,
    group_id parameter, and edge cases.
    """

    def setUp(self):
        self._create_fixtures()
        self.url = reverse("dashboard-progress")

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_has_required_fields(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        for field in ("completion_rate", "completed_tasks", "total_tasks",
                      "current_stage", "next_milestone", "scope", "updated_at"):
            self.assertIn(field, data, msg=f"Missing field: {field}")

    def test_completion_rate_calculated_correctly(self):
        """1 of 2 tasks with status=done → 50 %."""
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["completed_tasks"], 1)
        self.assertEqual(data["total_tasks"], 2)
        self.assertEqual(data["completion_rate"], 50)

    def test_current_stage_is_first_incomplete_milestone(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        # milestone (Week 1) is not completed → should be current stage
        self.assertEqual(data["current_stage"], "Week 1")

    def test_next_milestone_has_id_name_due_date(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        nm = data["next_milestone"]
        self.assertIsNotNone(nm)
        self.assertEqual(nm["id"], self.milestone.id)
        self.assertEqual(nm["name"], "Week 1")
        self.assertIsNotNone(nm["due_date"])

    def test_next_milestone_null_when_none_have_due_date(self):
        """If no incomplete milestone has a due_date, next_milestone must be null."""
        self.milestone.due_date = None
        self.milestone.save(update_fields=["due_date"])
        self.milestone2.due_date = None
        self.milestone2.save(update_fields=["due_date"])
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertIsNone(data["next_milestone"])

    def test_current_stage_complete_when_all_milestones_done(self):
        self.milestone.completed = True
        self.milestone.save(update_fields=["completed"])
        self.milestone2.completed = True
        self.milestone2.save(update_fields=["completed"])
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["current_stage"], "Complete")

    def test_zero_counts_when_user_has_no_groups(self):
        lone_user = User.objects.create_user(
            email="lone@dash.test", password="pass", first_name="Lone", last_name="Wolf"
        )
        self.client.force_authenticate(user=lone_user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["completion_rate"], 0)
        self.assertEqual(data["total_tasks"], 0)
        self.assertIsNone(data["next_milestone"])

    def test_zero_completion_when_group_has_no_tasks(self):
        empty_group = Groups.objects.create(group_name="Empty Group", track=self.track)
        Milestone.objects.create(
            group=empty_group, milestone_name="Empty MS", sort_order=1
        )
        # Use a fresh user who belongs only to the empty group so that self.group's
        # tasks (1 done / 1 todo) don't bleed into this snapshot and inflate the rate.
        lone_user = User.objects.create_user(
            email="lone3@dash.test", password="pass", first_name="Lone", last_name="Wolf"
        )
        GroupMembership.objects.create(
            group=empty_group, user=lone_user, membership_role="member"
        )
        self.client.force_authenticate(user=lone_user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["completion_rate"], 0)

    def test_group_id_param_scopes_to_single_group(self):
        """?group_id= must restrict the snapshot to that group only."""
        other_group = Groups.objects.create(group_name="Other Group", track=self.track)
        other_ms = Milestone.objects.create(
            group=other_group, milestone_name="Other MS", sort_order=1,
            due_date=timezone.now() + timezone.timedelta(days=5),
        )
        # Task with status=done in another group — must not bleed into scoped snapshot
        Tasks.objects.create(
            task_name="Other task",
            due_date=timezone.now() + timezone.timedelta(days=5),
            milestone=other_ms,
            status=Tasks.Status.DONE,
        )
        GroupMembership.objects.create(
            group=other_group, user=self.user, membership_role="member"
        )
        self.client.force_authenticate(user=self.user)
        # Scope to original group only — other_group tasks must not bleed in
        data = self.client.get(self.url, {"group_id": self.group.id}).json()
        self.assertEqual(data["total_tasks"], 2)
        self.assertEqual(data["scope"]["group_id"], self.group.id)

    def test_scope_contains_user_id_and_track_id(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        scope = data["scope"]
        self.assertEqual(scope["user_id"], self.user.id)
        self.assertEqual(scope["track_id"], self.track.id)

    def test_deleted_tasks_excluded_from_counts(self):
        """Tasks with deleted_at set must not count toward total_tasks."""
        Tasks.objects.create(
            task_name="Ghost task",
            due_date=timezone.now() + timezone.timedelta(days=1),
            milestone=self.milestone,
            deleted_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        # Soft-deleted task must not inflate total_tasks beyond the 2 active ones
        self.assertEqual(data["total_tasks"], 2)


# ---------------------------------------------------------------------------
# #2 – GET /dashboard/v1/next-event/
# ---------------------------------------------------------------------------

class NextEventTests(DashboardFixtureMixin, APITestCase):
    """
    Tests for the new Next Event endpoint.

    Covers authentication, the three relevance-filtering conditions
    (group, track, RSVP), admin bypass, and the 204 no-content case.
    """

    def setUp(self):
        self._create_fixtures()
        self.url = reverse("dashboard-next-event")

    def _make_future_event(self, name="Future Event", days_ahead=3, track=None):
        return Events.objects.create(
            event_name=name,
            start_datetime=timezone.now() + timezone.timedelta(days=days_ahead),
            ends_datetime=timezone.now() + timezone.timedelta(days=days_ahead, hours=2),
            track=track,
        )

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_relevant_events_returns_204(self):
        """A user with no groups, no track, and no RSVPs should receive HTTP 204."""
        lone_user = User.objects.create_user(
            email="lone2@dash.test", password="pass", first_name="Lone", last_name="Wolf"
        )
        self.client.force_authenticate(user=lone_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_returns_204_when_no_future_events_exist(self):
        # Relevant event targeting user's group but already ended
        past_event = Events.objects.create(
            event_name="Past",
            start_datetime=timezone.now() - timezone.timedelta(days=2),
            ends_datetime=timezone.now() - timezone.timedelta(days=1),
        )
        EventTargetGroup.objects.create(event=past_event, group=self.group)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_event_matched_via_group(self):
        """User should receive an event that targets their group (via EventTargetGroup)."""
        event = self._make_future_event("Group Event")
        EventTargetGroup.objects.create(event=event, group=self.group)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], event.id)

    def test_event_matched_via_track(self):
        """User should receive an event that targets their assigned track."""
        event = self._make_future_event("Track Event", track=self.track)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], event.id)

    def test_event_matched_via_rsvp(self):
        """User should receive an event they have an RSVP for, even without group/track match."""
        event = self._make_future_event("RSVP Event")
        EventRsvp.objects.create(event=event, user=self.user, rsvp_status="going")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], event.id)

    def test_earliest_event_returned_when_multiple_match(self):
        """Among multiple matching events the one starting soonest must be returned."""
        sooner = self._make_future_event("Sooner", days_ahead=1)
        later = self._make_future_event("Later", days_ahead=10)
        for ev in (sooner, later):
            EventTargetGroup.objects.create(event=ev, group=self.group)
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["id"], sooner.id)

    def test_response_includes_rsvp_status_pending_when_no_rsvp(self):
        """rsvp_status must default to 'pending' when no RSVP record exists."""
        event = self._make_future_event("No RSVP Event")
        EventTargetGroup.objects.create(event=event, group=self.group)
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["rsvp_status"], "pending")

    def test_response_includes_rsvp_status_from_existing_rsvp(self):
        event = self._make_future_event("Going Event")
        EventTargetGroup.objects.create(event=event, group=self.group)
        EventRsvp.objects.create(event=event, user=self.user, rsvp_status="going")
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["rsvp_status"], "going")

    def test_response_includes_group_from_event_target_group(self):
        event = self._make_future_event("Grouped Event")
        EventTargetGroup.objects.create(event=event, group=self.group)
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertEqual(data["group"], self.group.id)

    def test_group_is_null_when_event_has_no_target_group(self):
        event = self._make_future_event("Track-only Event", track=self.track)
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        self.assertIsNone(data["group"])

    def test_admin_receives_next_platform_wide_event(self):
        """Admin/staff users bypass relevance filtering and see the next event globally."""
        event = self._make_future_event("Platform Event")
        # No group or track targeting — irrelevant to non-admin users
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], event.id)

    def test_admin_returns_204_when_no_events_exist(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_response_includes_expected_event_fields(self):
        event = self._make_future_event("Field Check Event")
        EventTargetGroup.objects.create(event=event, group=self.group)
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url).json()
        for field in ("id", "event_name", "start_datetime", "ends_datetime",
                      "is_virtual", "rsvp_status", "group"):
            self.assertIn(field, data, msg=f"Missing field: {field}")
