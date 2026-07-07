from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import EventRsvp, EventTargetGroup, EventTargetRole, Events
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class DashboardNextEventApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
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

    def _create_event(self, name, *, start_in_days, event_format="virtual"):
        start = timezone.now() + timedelta(days=start_in_days)
        return Events.objects.create(
            event_name=name,
            start_datetime=start,
            ends_datetime=start + timedelta(hours=1),
            event_format=event_format,
        )

    def test_student_skips_mentor_only_event_and_returns_group_event(self):
        student = User.objects.create_user(
            email="student@test.com",
            password="pass123",
            first_name="Stu",
            last_name="Dent",
        )
        self._assign_role(student, self.student_role)
        group = Groups.objects.create(group_name="BTF046")
        GroupMembership.objects.create(group=group, user=student, membership_role="student")

        mentor_only = self._create_event("Mentor Sync", start_in_days=1)
        EventTargetRole.objects.create(event=mentor_only, role=self.mentor_role)

        group_event = self._create_event("Group Check-in", start_in_days=2)
        EventTargetGroup.objects.create(event=group_event, group=group)

        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_name"], "Group Check-in")
        self.assertEqual(
            sorted(response.data.keys()),
            [
                "description",
                "ends_datetime",
                "event_format",
                "event_image",
                "event_name",
                "event_type",
                "groups",
                "id",
                "location",
                "location_link",
                "rsvp_status",
                "start_datetime",
            ],
        )

    def test_mentor_invite_overrides_group_targeting(self):
        mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pass123",
            first_name="Men",
            last_name="Tor",
        )
        self._assign_role(mentor, self.mentor_role)
        group = Groups.objects.create(group_name="Mentor Group")
        GroupMembership.objects.create(group=group, user=mentor, membership_role="mentor")

        # Directly invited (RSVP) event the mentor is neither group- nor role-targeted for.
        invited_event = self._create_event("Special Invite", start_in_days=1)
        EventRsvp.objects.create(event=invited_event, user=mentor, rsvp_status=EventRsvp.RsvpStatus.PENDING)

        group_event = self._create_event("Regular Group Event", start_in_days=2)
        EventTargetGroup.objects.create(event=group_event, group=group)

        self.client.force_authenticate(user=mentor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_name"], "Special Invite")
        self.assertEqual(response.data["id"], invited_event.id)

    def test_admin_sees_earliest_event_regardless_of_targeting(self):
        admin = User.objects.create_user(
            email="admin@test.com",
            password="pass123",
            first_name="Ad",
            last_name="Min",
        )
        AdminScope.objects.create(user=admin)

        # A group the admin is not a member of, plus events targeted at it / at a role.
        other_group = Groups.objects.create(group_name="BTF099")

        role_event = self._create_event("Role Event", start_in_days=3)
        EventTargetRole.objects.create(event=role_event, role=self.mentor_role)

        group_event = self._create_event("Group Event", start_in_days=2)
        EventTargetGroup.objects.create(event=group_event, group=other_group)

        earliest = self._create_event("Earliest Event", start_in_days=1)
        EventTargetGroup.objects.create(event=earliest, group=other_group)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Any admin bypasses membership/role targeting → sees the earliest upcoming event.
        self.assertEqual(response.data["event_name"], earliest.event_name)
        self.assertIsNone(response.data["location"])

    def test_returns_204_when_user_has_no_relevant_upcoming_event(self):
        supervisor = User.objects.create_user(
            email="supervisor@test.com",
            password="pass123",
            first_name="Super",
            last_name="Visor",
        )
        self._assign_role(supervisor, self.supervisor_role)

        mentor_only_event = self._create_event("Mentor Only Event", start_in_days=1)
        EventTargetRole.objects.create(event=mentor_only_event, role=self.mentor_role)

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
    """End-to-end tests for ``GET /dashboard/v1/groups-preview/``."""

    url = "/dashboard/v1/groups-preview/"

    def setUp(self):
        self.client = APIClient()

        self.lead = User.objects.create_user(
            email="anita@test.com", password="pass123",
            first_name="Anita", last_name="Pickard",
        )
        self.member_a = User.objects.create_user(
            email="member-a@test.com", password="pass123",
            first_name="Mem", last_name="A",
        )
        self.member_b = User.objects.create_user(
            email="member-b@test.com", password="pass123",
            first_name="Mem", last_name="B",
        )
        self.member_c = User.objects.create_user(
            email="member-c@test.com", password="pass123",
            first_name="Mem", last_name="C",
        )
        self.viewer = User.objects.create_user(
            email="viewer@test.com", password="pass123",
            first_name="View", last_name="Er",
        )

        # Group BTF046: lead + 4 students = 5 active members, status=active
        self.group_btf046 = Groups.objects.create(group_name="BTF046")
        GroupMembership.objects.create(
            group=self.group_btf046, user=self.lead,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        for member in (self.member_a, self.member_b, self.member_c, self.viewer):
            GroupMembership.objects.create(
                group=self.group_btf046, user=member,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )

        # Group BTF047: lead + viewer = 2 active members; member_a has left
        self.group_btf047 = Groups.objects.create(group_name="BTF047")
        GroupMembership.objects.create(
            group=self.group_btf047, user=self.lead,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        GroupMembership.objects.create(
            group=self.group_btf047, user=self.viewer,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        # `joined_at` pinned to the past so the model's
        # `left_at >= joined_at` CHECK constraint is satisfied.
        now = timezone.now()
        GroupMembership.objects.create(
            group=self.group_btf047, user=self.member_a,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            joined_at=now - timedelta(days=1),
            left_at=now,
        )

        # Group BTF048: viewer only, NO mentor → status=inactive
        self.group_unmatched = Groups.objects.create(group_name="BTF048")
        GroupMembership.objects.create(
            group=self.group_unmatched, user=self.viewer,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        # Group VIC001: viewer is NOT a member; used for admin scoping tests
        self.group_vic = Groups.objects.create(group_name="VIC001")
        GroupMembership.objects.create(
            group=self.group_vic, user=self.member_a,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        # Soft-deleted group must never appear.
        # `created_at` pinned to the past for the model's
        # `deleted_at >= created_at` CHECK constraint.
        self.deleted_group = Groups.objects.create(
            group_name="ZZZ_DELETED",
            created_at=now - timedelta(days=2),
            deleted_at=now,
        )

    # ----- Auth ---------------------------------------------------------

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ----- Schema / contract -------------------------------------------

    def test_response_uses_paginated_wrapper(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(set(body.keys()), {"count", "next", "previous", "results"})

    def test_result_row_matches_spec_keys(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = response.json()["results"]
        self.assertGreater(len(rows), 0)
        self.assertEqual(
            set(rows[0].keys()),
            {
                "id", "group_name",
                "member_count", "lead_user", "lead_name", "status",
            },
        )

    def test_lead_user_is_nested_object_when_mentor_exists(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = response.json()["results"]
        btf046 = next(r for r in rows if r["group_name"] == "BTF046")
        self.assertEqual(
            btf046["lead_user"],
            {"id": self.lead.id, "first_name": "Anita", "last_name": "Pickard"},
        )
        self.assertEqual(btf046["lead_name"], "Anita Pickard")

    def test_lead_user_and_lead_name_are_null_when_no_mentor(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = response.json()["results"]
        unmatched = next(r for r in rows if r["group_name"] == "BTF048")
        self.assertIsNone(unmatched["lead_user"])
        self.assertIsNone(unmatched["lead_name"])

    def test_soft_deleted_groups_excluded(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        names = {r["group_name"] for r in response.json()["results"]}
        self.assertNotIn("ZZZ_DELETED", names)

    # ----- Status tri-state --------------------------------------------

    def test_status_active_when_group_has_mentor(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = {r["group_name"]: r for r in response.json()["results"]}
        self.assertEqual(rows["BTF046"]["status"], "active")
        self.assertEqual(rows["BTF047"]["status"], "active")

    def test_status_inactive_when_group_has_no_mentor(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = {r["group_name"]: r for r in response.json()["results"]}
        self.assertEqual(rows["BTF048"]["status"], "inactive")

    # ----- member_count aggregation ------------------------------------

    def test_member_count_uses_db_annotation_and_excludes_left_members(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true")
        rows = {r["group_name"]: r for r in response.json()["results"]}
        # BTF046: lead + 4 students = 5
        self.assertEqual(rows["BTF046"]["member_count"], 5)
        # BTF047: lead + viewer (member_a left) = 2
        self.assertEqual(rows["BTF047"]["member_count"], 2)
        # BTF048: viewer only = 1
        self.assertEqual(rows["BTF048"]["member_count"], 1)

    def test_member_count_does_not_scale_with_group_count(self):
        """Regression guard against N+1: query count must not grow linearly."""
        self.client.force_authenticate(user=self.viewer)
        self.client.get(self.url + "?mine=true")  # warm caches

        with CaptureQueriesContext(connection) as ctx_small:
            self.client.get(self.url + "?mine=true")
        baseline = len(ctx_small.captured_queries)

        for i in range(8):
            extra = Groups.objects.create(group_name=f"BTF1{i:02d}")
            GroupMembership.objects.create(
                group=extra, user=self.lead,
                membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            )
            GroupMembership.objects.create(
                group=extra, user=self.viewer,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )

        with CaptureQueriesContext(connection) as ctx_large:
            response = self.client.get(self.url + "?mine=true")
        scaled = len(ctx_large.captured_queries)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(scaled, baseline + 2)

    # ----- Input validation (covers PR-11's `or 20` zero-bug) ----------

    def test_page_size_zero_returns_400(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?page_size=0")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_page_size_negative_returns_400(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?page_size=-1")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_page_size_above_max_returns_400(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?page_size=1000")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_page_size_string_returns_400(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?page_size=abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ----- Scoping matrix ----------------------------------------------

    def test_non_admin_only_sees_own_groups_regardless_of_mine_flag(self):
        self.client.force_authenticate(user=self.viewer)
        for query in ("", "?mine=true", "?mine=false"):
            response = self.client.get(self.url + query)
            names = {r["group_name"] for r in response.json()["results"]}
            self.assertEqual(names, {"BTF046", "BTF047", "BTF048"}, msg=f"query={query!r}")
            self.assertNotIn("VIC001", names)

    def test_admin_without_mine_sees_all_active_groups(self):
        admin = User.objects.create_user(
            email="admin-scope@test.com", password="pass",
            first_name="A", last_name="S",
        )
        AdminScope.objects.create(user=admin)
        self.client.force_authenticate(user=admin)

        response = self.client.get(self.url)
        names = {r["group_name"] for r in response.json()["results"]}
        # Single-tier admin without ``mine`` sees every active group, including
        # ones they are not a member of. Soft-deleted groups stay excluded.
        self.assertEqual(names, {"BTF046", "BTF047", "BTF048", "VIC001"})
        self.assertNotIn("ZZZ_DELETED", names)

    def test_admin_with_mine_only_sees_memberships(self):
        admin = User.objects.create_user(
            email="admin-mine@test.com", password="pass",
            first_name="A", last_name="M",
        )
        AdminScope.objects.create(user=admin)
        GroupMembership.objects.create(
            group=self.group_vic, user=admin,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.client.force_authenticate(user=admin)

        response = self.client.get(self.url + "?mine=true")
        names = {r["group_name"] for r in response.json()["results"]}
        self.assertEqual(names, {"VIC001"})

    # ----- Pagination ---------------------------------------------------

    def test_pagination_page_size_limits_results_and_signals_next(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true&page_size=1")
        body = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["count"], 3)  # BTF046, BTF047, BTF048
        self.assertEqual(body["next"], 2)
        self.assertIsNone(body["previous"])

    def test_pagination_second_page_signals_previous(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url + "?mine=true&page_size=1&page=2")
        body = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["previous"], 1)
        self.assertEqual(body["next"], 3)

    def test_empty_results_when_user_has_no_groups(self):
        loner = User.objects.create_user(
            email="loner@test.com", password="pass",
            first_name="Lo", last_name="Ner",
        )
        self.client.force_authenticate(user=loner)
        response = self.client.get(self.url)
        body = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["results"], [])


# ---------------------------------------------------------------------------
# Progress API tests
# ---------------------------------------------------------------------------
from apps.users.models import MentorProfile
from apps.tasks.models import CreatorRole, Task, TaskType

class DashboardProgressApiTests(TestCase):
    url = "/dashboard/v1/progress/"

    def setUp(self):
        self.client = APIClient()

        self.student = User.objects.create_user(
            email="student_prog@test.com",
            password="pass123",
            first_name="Stu",
            last_name="Dent",
        )
        self.mentor = User.objects.create_user(
            email="mentor_prog@test.com",
            password="pass123",
            first_name="Men",
            last_name="Tor",
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="University of Sydney",
            mentor_reason="I like mentoring",
        )
        self.group = Groups.objects.create(group_name="BTF046_Prog")
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
    def _create_task(self, *, completed=False, days_from_now=7, name="Test Task"):
        return Task.objects.create(
            name=name,
            task_type=TaskType.GROUP,
            group=self.group,
            due_date=timezone.now() + timedelta(days=days_from_now),
            completed=completed,
            creator_role=CreatorRole.GLOBAL_ADMIN,
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
            {"completionRate", "completedTasks", "totalTasks", "currentWeek", "nextTask", "nextTaskDate"},
        )

    def test_student_can_access_own_group(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_other_group(self):
        other_group = Groups.objects.create(group_name="OtherGroup")
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

    def test_next_task_returned(self):
        self._create_task(completed=False, name="Check-in #1")
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url + f"?group_id={self.group.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nextTask"], "Check-in #1")
