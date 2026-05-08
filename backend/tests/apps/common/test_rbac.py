from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.rbac import (
    active_role_ids,
    active_role_names,
    group_participant_qs,
    is_global_admin,
    track_admin_track_ids,
)
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class CommonRBACTests(TestCase):
    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.primary_track = Tracks.objects.create(track_name="Primary", state=self.state)
        self.secondary_track = Tracks.objects.create(track_name="Secondary", state=self.state)
        self.group = Groups.objects.create(group_name="Primary Group", track=self.primary_track)

        self.global_user = User.objects.create_user(
            email="global-admin@test.com",
            password="pw",
            first_name="Global",
            last_name="Admin",
        )
        self.track_admin = User.objects.create_user(
            email="track-admin@test.com",
            password="pw",
            first_name="Track",
            last_name="Admin",
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pw",
            first_name="Mentor",
            last_name="User",
            track=self.primary_track,
        )

        self.admin_role = Roles.objects.create(role_name="admin")
        self.mentor_role = Roles.objects.create(role_name="mentor")
        now = timezone.now()
        future = now + timedelta(days=365)

        AdminScope.objects.create(user=self.global_user, is_global=True)
        AdminScope.objects.create(user=self.track_admin, track=self.primary_track, is_global=False)
        RoleAssignmentHistory.objects.create(user=self.mentor, role=self.mentor_role, valid_from=now, valid_to=future)
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role="mentor")

    def test_is_global_admin_accepts_global_admin_scope(self):
        self.assertTrue(is_global_admin(self.global_user))
        self.assertFalse(is_global_admin(self.track_admin))

    def test_active_role_helpers_resolve_current_role_assignments(self):
        self.assertEqual(active_role_names(self.mentor), {"mentor"})
        self.assertEqual(active_role_ids(self.mentor), {self.mentor_role.id})

    def test_group_participant_qs_only_returns_active_memberships(self):
        self.assertTrue(group_participant_qs(self.mentor, self.group.id).exists())
        membership = GroupMembership.objects.get(user=self.mentor, group=self.group, left_at__isnull=True)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])

        self.assertFalse(group_participant_qs(self.mentor, self.group.id).exists())

    def test_track_admin_track_ids_returns_scoped_tracks_only_for_non_global_admin(self):
        self.assertEqual(track_admin_track_ids(self.track_admin), {self.primary_track.id})
        self.assertEqual(track_admin_track_ids(self.global_user), set())
