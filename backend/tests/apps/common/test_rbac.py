from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.rbac import (
    active_role_ids,
    active_role_names,
    get_active_role_name,
    group_participant_qs,
    is_global_admin,
    track_admin_track_ids,
    user_has_role,
)
from apps.common.role_names import (
    ROLE_MENTOR,
    ROLE_STUDENT,
    get_role_by_name,
    try_get_role_by_name,
)
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope
from apps.users.utils.admin_scope import (
    get_admin_track_ids as get_operational_admin_track_ids,
    is_operational_admin,
)


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

    def test_is_global_admin_ignores_is_staff_and_is_superuser(self):
        staff_user = User.objects.create_user(email="staff@test.com", password="pw", is_staff=True)
        super_user = User.objects.create_user(email="super@test.com", password="pw", is_superuser=True)
        self.assertFalse(is_global_admin(staff_user))
        self.assertFalse(is_global_admin(super_user))
        self.assertEqual(track_admin_track_ids(staff_user), set())
        self.assertEqual(track_admin_track_ids(super_user), set())

    def test_operational_admin_helper_requires_admin_scope(self):
        staff_user = User.objects.create_user(email="ops-staff@test.com", password="pw", is_staff=True)
        scoped_user = User.objects.create_user(email="ops-track@test.com", password="pw")
        AdminScope.objects.create(user=scoped_user, track=self.primary_track, is_global=False)

        self.assertFalse(is_operational_admin(staff_user))
        self.assertEqual(get_operational_admin_track_ids(staff_user), [])
        self.assertTrue(is_operational_admin(scoped_user))
        self.assertEqual(get_operational_admin_track_ids(scoped_user), [self.primary_track.id])

    def test_is_global_admin_ignores_role_assignments(self):
        admin_role = Roles.objects.create(role_name="global_admin")
        user = User.objects.create_user(email="role-admin@test.com", password="pw")
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=user, role=admin_role, valid_from=now, valid_to=now + timedelta(days=365)
        )
        self.assertFalse(is_global_admin(user))

    def test_get_active_role_name_returns_normalized_role(self):
        self.assertEqual(get_active_role_name(self.mentor), ROLE_MENTOR)

    def test_get_active_role_name_handles_anonymous_and_no_role(self):
        no_role_user = User.objects.create_user(email="noroles@test.com", password="pw")
        self.assertIsNone(get_active_role_name(no_role_user))
        self.assertIsNone(get_active_role_name(None))

    def test_user_has_role_matches_active_roles_case_insensitively(self):
        self.assertTrue(user_has_role(self.mentor, "MENTOR"))
        self.assertFalse(user_has_role(self.mentor, ROLE_STUDENT))
        self.assertFalse(user_has_role(self.mentor))

    def test_role_name_lookup_is_case_insensitive_and_pk_independent(self):
        # Force a different PK ordering than the names imply to prove we
        # do not rely on numeric IDs.
        Roles.objects.create(role_name="filler-role-1")
        Roles.objects.create(role_name="filler-role-2")
        student = Roles.objects.create(role_name="Student")

        self.assertEqual(get_role_by_name("student"), student)
        self.assertEqual(get_role_by_name("STUDENT"), student)
        self.assertIsNone(try_get_role_by_name("does-not-exist"))
