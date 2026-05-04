from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.events.models import EventRsvp, EventTargetGroup, EventTargetRole, Events
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class DashboardNextEventApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.primary_track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)
        self.secondary_track = Tracks.objects.create(track_name="AUS-ALT", state=self.state)
        self.student_role = Roles.objects.create(role_name="student")
        self.mentor_role = Roles.objects.create(role_name="mentor")
        self.supervisor_role = Roles.objects.create(role_name="supervisor")
        self.url = reverse("dashboard-next-event")

    def _assign_role(self, user, role):
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=now - timedelta(minutes=5),
            valid_to=now + timedelta(days=30),
        )

    def _create_event(self, name, *, start_in_days, track=None, is_virtual=True):
        start = timezone.now() + timedelta(days=start_in_days)
        return Events.objects.create(
            event_name=name,
            track=track,
            start_datetime=start,
            ends_datetime=start + timedelta(hours=1),
            is_virtual=is_virtual,
        )

    def test_student_skips_mentor_only_event_and_returns_group_event(self):
        student = User.objects.create_user(
            email="student@test.com",
            password="pass123",
            first_name="Stu",
            last_name="Dent",
            track=self.primary_track,
        )
        self._assign_role(student, self.student_role)
        group = Groups.objects.create(group_name="BTF046", track=self.primary_track)
        GroupMembership.objects.create(group=group, user=student, membership_role="student")

        mentor_only = self._create_event("Mentor Sync", start_in_days=1, track=self.primary_track)
        EventTargetRole.objects.create(event=mentor_only, role=self.mentor_role)

        group_event = self._create_event("Group Check-in", start_in_days=2, track=self.primary_track)
        EventTargetGroup.objects.create(event=group_event, group=group)

        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_name"], "Group Check-in")
        self.assertEqual(sorted(response.data.keys()), ["event_name", "id", "is_virtual", "location", "location_link", "start_datetime"])

    def test_mentor_invite_overrides_track_and_group_targeting(self):
        mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pass123",
            first_name="Men",
            last_name="Tor",
            track=self.primary_track,
        )
        self._assign_role(mentor, self.mentor_role)
        group = Groups.objects.create(group_name="Mentor Group", track=self.primary_track)
        GroupMembership.objects.create(group=group, user=mentor, membership_role="mentor")

        invited_event = self._create_event("Special Invite", start_in_days=1, track=self.secondary_track)
        EventRsvp.objects.create(event=invited_event, user=mentor, rsvp_status=EventRsvp.RsvpStatus.PENDING)

        group_event = self._create_event("Regular Group Event", start_in_days=2, track=self.primary_track)
        EventTargetGroup.objects.create(event=group_event, group=group)

        self.client.force_authenticate(user=mentor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_name"], "Special Invite")
        self.assertEqual(response.data["id"], invited_event.id)

    def test_track_scoped_admin_sees_platform_wide_event_before_other_track_event(self):
        admin = User.objects.create_user(
            email="scoped-admin@test.com",
            password="pass123",
            first_name="Scoped",
            last_name="Admin",
        )
        AdminScope.objects.create(user=admin, track=self.primary_track, is_global=False)

        self._create_event("Other Track Event", start_in_days=1, track=self.secondary_track)
        platform_event = self._create_event("Platform Event", start_in_days=2, track=None)
        self._create_event("Primary Track Event", start_in_days=3, track=self.primary_track)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_name"], platform_event.event_name)
        self.assertIsNone(response.data["location"])

    def test_returns_204_when_user_has_no_relevant_upcoming_event(self):
        supervisor = User.objects.create_user(
            email="supervisor@test.com",
            password="pass123",
            first_name="Super",
            last_name="Visor",
            track=self.primary_track,
        )
        self._assign_role(supervisor, self.supervisor_role)

        other_track_event = self._create_event("Other Track Event", start_in_days=1, track=self.secondary_track)
        EventTargetRole.objects.create(event=other_track_event, role=self.mentor_role)

        self.client.force_authenticate(user=supervisor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_summary_returns_authenticated_user_summary(self):
        user = User.objects.create_user(
            email="summary@test.com",
            password="pass123",
            first_name="Dash",
            last_name="Board",
        )

        self.client.force_authenticate(user=user)
        response = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], user.email)
        self.assertEqual(response.data["stats"], {"tasks": 0, "events": 0, "groups": 0})

class GroupsPreviewViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/dashboard/v1/groups-preview/"
        self.user = User.objects.create_user(
            email="test@test.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_403(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_returns_paginated_response(self, mock_service):
        mock_service.return_value = [
            {
                "id": 1,
                "name": "BTF046",
                "track_id": 1,
                "track_name": "AUS-NSW",
                "member_count": 4,
                "lead_name": "Anita Pickard",
                "status": "active",
            }
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "BTF046")
        self.assertEqual(data["results"][0]["track_name"], "AUS-NSW")
        self.assertEqual(data["results"][0]["member_count"], 4)
        self.assertEqual(data["results"][0]["lead_name"], "Anita Pickard")
        self.assertEqual(data["results"][0]["status"], "active")

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_param_passed_to_service(self, mock_service):
        mock_service.return_value = []
        self.client.get(self.url + "?mine=true")
        mock_service.assert_called_once_with(user=self.user, mine=True)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_false_by_default(self, mock_service):
        mock_service.return_value = []
        self.client.get(self.url)
        mock_service.assert_called_once_with(user=self.user, mine=False)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_pagination_page_size(self, mock_service):
        mock_service.return_value = [
            {
                "id": i,
                "name": f"Group{i}",
                "track_id": 1,
                "track_name": "AUS-NSW",
                "member_count": 2,
                "lead_name": None,
                "status": "active",
            }
            for i in range(10)
        ]
        response = self.client.get(self.url + "?page_size=3")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["count"], 10)
        self.assertIsNotNone(data["next"])

    @patch("apps.dashboard.views.get_groups_preview")
    def test_empty_results(self, mock_service):
        mock_service.return_value = []
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])


# ---------------------------------------------------------------------------
# Progress API tests
# ---------------------------------------------------------------------------
from apps.users.models import MentorProfile
from apps.tasks.models import Milestone, Tasks

class DashboardProgressApiTests(TestCase):
    url = "/dashboard/v1/progress/"

    def setUp(self):
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)

        self.student = User.objects.create_user(
            email="student_prog@test.com",
            password="pass123",
            first_name="Stu",
            last_name="Dent",
            track=self.track,
        )
        self.mentor = User.objects.create_user(
            email="mentor_prog@test.com",
            password="pass123",
            first_name="Men",
            last_name="Tor",
            track=self.track,
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="University of Sydney",
            mentor_reason="I like mentoring",
        )
        self.group = Groups.objects.create(group_name="BTF046_Prog", track=self.track)
        GroupMembership.objects.create(
            group=self.group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        GroupMembership.objects.create(
            group=self.group,
            user=self.student,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.milestone = Milestone.objects.create(
            group=self.group,
            milestone_name="Check-in #1",
        )

    def _create_task(self, *, completed=False, days_from_now=7):
        due = timezone.now() + timedelta(days=days_from_now)
        return Tasks.objects.create(
            task_name="Test Task",
            due_date=due,
            milestone=self.milestone,
            completed=completed,
        )

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_has_correct_schema(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {"completionRate", "completedTasks", "totalTasks", "currentWeek", "nextMilestone", "nextMilestoneDate"},
        )

    def test_student_can_access_own_group(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_other_group(self):
        other_track = Tracks.objects.create(track_name="AUS-VIC", state=self.state)
        other_group = Groups.objects.create(group_name="OtherGroup", track=other_track)
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={other_group.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_completion_rate_calculated_correctly(self):
        self._create_task(completed=True)
        self._create_task(completed=True)
        self._create_task(completed=False)
        self._create_task(completed=False)
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["completionRate"], 50)
        self.assertEqual(response.data["completedTasks"], 2)
        self.assertEqual(response.data["totalTasks"], 4)

    def test_completion_rate_zero_when_no_tasks(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["completionRate"], 0)
        self.assertEqual(response.data["totalTasks"], 0)

    def test_next_milestone_returned(self):
        self._create_task(completed=False)
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nextMilestone"], "Check-in #1")