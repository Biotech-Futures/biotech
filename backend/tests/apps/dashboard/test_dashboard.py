from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.dashboard.serializers import DashboardGroupPreviewSerializer
from apps.dashboard.services import get_groups_preview
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
        self.assertEqual(sorted(response.data.keys()), ["event_name", "id", "is_virtual", "link", "location", "start_datetime"])

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


class DashboardGroupsPreviewApiTests(TestCase):
    """
    End-to-end coverage for the flattened groups-preview projection.

    Covers the service-layer annotations (member_count + lead_user_* fields),
    the UI-specific serializer shape, and the view's scoping / filtering
    behaviour. Uses real database fixtures so that the DB-level aggregation
    contract is actually exercised.
    """

    url = "/dashboard/v1/groups-preview/"

    def setUp(self):
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_nsw = Tracks.objects.create(track_name="AUS-NSW", state=self.state)
        self.track_vic = Tracks.objects.create(track_name="AUS-VIC", state=self.state)

        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pass123",
            first_name="Anita",
            last_name="Pickard",
            track=self.track_nsw,
        )
        self.student_a = User.objects.create_user(
            email="student.a@test.com",
            password="pass123",
            first_name="Alice",
            last_name="Ng",
            track=self.track_nsw,
        )
        self.student_b = User.objects.create_user(
            email="student.b@test.com",
            password="pass123",
            first_name="Bob",
            last_name="Tan",
            track=self.track_nsw,
        )
        self.student_c = User.objects.create_user(
            email="student.c@test.com",
            password="pass123",
            first_name="Cara",
            last_name="Lin",
            track=self.track_nsw,
        )

    def _make_group(self, name, track, *, members=(), mentor=None, mentor_left=False,
                    deleted=False):
        # Place `joined_at` safely in the past so that a simultaneous
        # `left_at = now()` still satisfies the CHECK constraint on
        # GroupMembership (left_at >= joined_at).
        joined_at = timezone.now() - timedelta(days=1)

        group = Groups.objects.create(group_name=name, track=track)
        if deleted:
            group.deleted_at = timezone.now()
            group.save(update_fields=["deleted_at"])
        if mentor is not None:
            GroupMembership.objects.create(
                group=group,
                user=mentor,
                membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
                joined_at=joined_at,
                left_at=timezone.now() if mentor_left else None,
            )
        for user in members:
            GroupMembership.objects.create(
                group=group,
                user=user,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                joined_at=joined_at,
            )
        return group

    # ------------------------------------------------------------------ #
    # Service-layer annotations
    # ------------------------------------------------------------------ #

    def test_service_annotates_member_count_for_active_members_only(self):
        group = self._make_group(
            "BTF046",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_a, self.student_b],
        )
        joined_at = timezone.now() - timedelta(days=1)
        GroupMembership.objects.create(
            group=group,
            user=self.student_c,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            joined_at=joined_at,
            left_at=timezone.now(),
        )

        row = get_groups_preview(user=self.mentor).get(pk=group.pk)

        # 1 mentor + 2 active students. The left student is excluded.
        self.assertEqual(row.member_count, 3)

    def test_service_exposes_flattened_lead_user_fields(self):
        group = self._make_group("BTF046", self.track_nsw, mentor=self.mentor)

        row = get_groups_preview(user=self.mentor).get(pk=group.pk)

        self.assertEqual(row.lead_user_id, self.mentor.id)
        self.assertEqual(row.lead_first_name, "Anita")
        self.assertEqual(row.lead_last_name, "Pickard")

    def test_service_lead_user_null_when_no_active_mentor(self):
        group = self._make_group(
            "NoLead",
            self.track_nsw,
            mentor=self.mentor,
            mentor_left=True,
            members=[self.student_a],
        )
        self.client.force_authenticate(user=self.student_a)

        row = get_groups_preview(user=self.student_a).get(pk=group.pk)

        self.assertIsNone(row.lead_user_id)
        self.assertIsNone(row.lead_first_name)
        self.assertIsNone(row.lead_last_name)

    def test_service_excludes_soft_deleted_groups(self):
        self._make_group("Alive", self.track_nsw, members=[self.student_a])
        self._make_group(
            "Dead",
            self.track_nsw,
            members=[self.student_a],
            deleted=True,
        )

        names = list(
            get_groups_preview(user=self.student_a).values_list("group_name", flat=True)
        )
        self.assertEqual(names, ["Alive"])

    def test_service_track_id_filter_scopes_results(self):
        self._make_group("NSW-1", self.track_nsw, members=[self.student_a])
        self._make_group("VIC-1", self.track_vic, members=[self.student_a])

        # As a plain member, both groups are in their own membership scope.
        qs = get_groups_preview(user=self.student_a, track_id=self.track_nsw.id)
        self.assertEqual(list(qs.values_list("group_name", flat=True)), ["NSW-1"])

    # ------------------------------------------------------------------ #
    # Serializer flattening
    # ------------------------------------------------------------------ #

    def test_serializer_produces_flattened_ui_schema(self):
        group = self._make_group(
            "BTF046",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_a, self.student_b],
        )

        obj = get_groups_preview(user=self.mentor).get(pk=group.pk)
        data = DashboardGroupPreviewSerializer(obj).data

        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "group_name",
                "track_id",
                "track_name",
                "member_count",
                "lead_user",
                "lead_name",
                "status",
            },
        )
        self.assertEqual(data["id"], group.id)
        self.assertEqual(data["group_name"], "BTF046")
        self.assertEqual(data["track_id"], self.track_nsw.id)
        self.assertEqual(data["track_name"], "AUS-NSW")
        self.assertEqual(data["member_count"], 3)
        self.assertEqual(
            data["lead_user"],
            {"id": self.mentor.id, "first_name": "Anita", "last_name": "Pickard"},
        )
        self.assertEqual(data["lead_name"], "Anita Pickard")
        self.assertEqual(data["status"], "active")

    def test_serializer_lead_fields_null_when_no_mentor(self):
        group = self._make_group("NoLead", self.track_nsw, members=[self.student_a])

        obj = get_groups_preview(user=self.student_a).get(pk=group.pk)
        data = DashboardGroupPreviewSerializer(obj).data

        self.assertIsNone(data["lead_user"])
        self.assertIsNone(data["lead_name"])

    # ------------------------------------------------------------------ #
    # View / HTTP integration
    # ------------------------------------------------------------------ #

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_sees_only_own_groups(self):
        mine = self._make_group(
            "Mine",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_a],
        )
        self._make_group(
            "Other",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_b],
        )

        self.client.force_authenticate(user=self.student_a)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["group_name"] for row in response.data["results"]]
        self.assertEqual(names, ["Mine"])
        self.assertEqual(response.data["results"][0]["id"], mine.id)

    def test_scoped_admin_sees_all_groups_in_track_scope(self):
        admin = User.objects.create_user(
            email="scoped-admin@test.com",
            password="pass123",
            first_name="Scoped",
            last_name="Admin",
        )
        AdminScope.objects.create(user=admin, track=self.track_nsw, is_global=False)

        self._make_group("NSW-A", self.track_nsw, members=[self.student_a])
        self._make_group("NSW-B", self.track_nsw, members=[self.student_b])
        self._make_group("VIC-1", self.track_vic, members=[self.student_c])

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["group_name"] for row in response.data["results"]]
        self.assertEqual(sorted(names), ["NSW-A", "NSW-B"])

    def test_admin_with_mine_true_only_sees_own_memberships(self):
        admin = User.objects.create_user(
            email="admin-mentor@test.com",
            password="pass123",
            first_name="Admin",
            last_name="Mentor",
        )
        AdminScope.objects.create(user=admin, track=self.track_nsw, is_global=False)

        self._make_group("NotMine", self.track_nsw, members=[self.student_a])
        mine_group = Groups.objects.create(group_name="Mine", track=self.track_nsw)
        GroupMembership.objects.create(
            group=mine_group,
            user=admin,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url + "?mine=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["group_name"] for row in response.data["results"]]
        self.assertEqual(names, ["Mine"])

    def test_track_id_query_param_filters_results(self):
        admin = User.objects.create_user(
            email="global-admin@test.com",
            password="pass123",
            first_name="Global",
            last_name="Admin",
            is_staff=True,
        )
        self._make_group("NSW-1", self.track_nsw, members=[self.student_a])
        self._make_group("VIC-1", self.track_vic, members=[self.student_b])

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url + f"?track_id={self.track_nsw.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["group_name"] for row in response.data["results"]]
        self.assertEqual(names, ["NSW-1"])

    def test_track_id_non_integer_returns_400(self):
        self.client.force_authenticate(user=self.student_a)
        response = self.client.get(self.url + "?track_id=not-an-int")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_matches_spec_shape(self):
        self._make_group(
            "BTF046",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_a, self.student_b, self.student_c],
        )

        self.client.force_authenticate(user=self.mentor)
        response = self.client.get(self.url + f"?track_id={self.track_nsw.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()), {"count", "next", "previous", "results"}
        )
        self.assertEqual(len(response.data["results"]), 1)

        row = response.data["results"][0]
        self.assertEqual(
            set(row.keys()),
            {
                "id",
                "group_name",
                "track_id",
                "track_name",
                "member_count",
                "lead_user",
                "lead_name",
                "status",
            },
        )
        self.assertEqual(row["group_name"], "BTF046")
        self.assertEqual(row["track_name"], "AUS-NSW")
        self.assertEqual(row["member_count"], 4)
        self.assertEqual(
            row["lead_user"],
            {"id": self.mentor.id, "first_name": "Anita", "last_name": "Pickard"},
        )
        self.assertEqual(row["lead_name"], "Anita Pickard")
        self.assertEqual(row["status"], "active")

    def test_pagination_respects_page_size(self):
        admin = User.objects.create_user(
            email="pag-admin@test.com",
            password="pass123",
            first_name="Pag",
            last_name="Admin",
            is_staff=True,
        )
        for i in range(5):
            self._make_group(f"G{i:02d}", self.track_nsw, members=[self.student_a])

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url + "?page_size=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["next"], 2)
        self.assertIsNone(response.data["previous"])

    # ------------------------------------------------------------------ #
    # Query efficiency — validates the "no Python loops" aggregation goal
    # ------------------------------------------------------------------ #

    def test_query_count_is_bounded_regardless_of_group_count(self):
        """
        Each row of the preview adds only annotations/joins, not extra round
        trips. Growing the number of groups must not grow the query count,
        which is the core promise of moving aggregation to the DB.
        """
        admin = User.objects.create_user(
            email="qc-admin@test.com",
            password="pass123",
            first_name="QC",
            last_name="Admin",
            is_staff=True,
        )

        self._make_group(
            "solo",
            self.track_nsw,
            mentor=self.mentor,
            members=[self.student_a],
        )

        self.client.force_authenticate(user=admin)

        # Warm the client up once so session/CSRF setup doesn't pollute the
        # measured query counts on the first "real" request.
        self.client.get(self.url + "?page_size=50")

        with CaptureQueriesContext(connection) as ctx_one:
            response_one = self.client.get(self.url + "?page_size=50")
        self.assertEqual(response_one.status_code, status.HTTP_200_OK)
        baseline = len(ctx_one.captured_queries)

        for i in range(9):
            extra_mentor = User.objects.create_user(
                email=f"mentor{i}@test.com",
                password="pass123",
                first_name=f"M{i}",
                last_name="Entor",
            )
            self._make_group(
                f"g{i:02d}",
                self.track_nsw,
                mentor=extra_mentor,
                members=[self.student_a, self.student_b, self.student_c],
            )

        with CaptureQueriesContext(connection) as ctx_many:
            response_many = self.client.get(self.url + "?page_size=50")
        self.assertEqual(response_many.status_code, status.HTTP_200_OK)
        self.assertEqual(response_many.data["count"], 10)

        scaled = len(ctx_many.captured_queries)
        self.assertEqual(
            scaled,
            baseline,
            msg=(
                "Groups-preview query count should not grow with the number of "
                f"groups. Baseline={baseline}, scaled={scaled}. Queries:\n"
                + "\n".join(q["sql"] for q in ctx_many.captured_queries)
            ),
        )
