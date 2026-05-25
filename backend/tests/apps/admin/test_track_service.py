"""Tests for ``apps.admin.services.track``.

Focus: archiving a track must force-logout every affected user (direct
``User.track`` and indirect via active ``GroupMembership``), while sparing
operational admins so they don't accidentally lock themselves out by
archiving their own track.
"""
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone

from apps.admin.services import track as track_service
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.user_sessions.models import UserSession
from apps.users.models import AdminScope, User


def _seed_django_session(user) -> str:
    """Create a real django_session row mapped to ``user``. Returns the key.

    Mirrors what Django's ``login()`` does at the storage layer: stash
    ``_auth_user_id`` (and the friends Django expects) in a fresh session
    so ``_flush_django_sessions_for_user`` can find and delete it by
    scanning ``django_session`` rows.
    """
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store["_auth_user_backend"] = "apps.users.backends.CachedModelBackend"
    store["_auth_user_hash"] = user.get_session_auth_hash()
    store.create()
    return store.session_key


class ArchiveTrackSessionTerminationTests(TestCase):
    """``archive_track`` must boot users out of any live session."""

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-A", state=state)
        self.other_track = Tracks.objects.create(track_name="TRACK-B", state=state)

        self.global_admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="adminpass",
        )
        AdminScope.objects.create(user=self.global_admin, is_global=True)

    # --- direct membership ---

    def test_archive_revokes_user_sessions_for_users_on_track(self):
        student = User.objects.create_user(
            email="student@example.com",
            first_name="Sam",
            last_name="Student",
            track=self.track,
            password="testpass",
        )
        open_session = UserSession.objects.create(user=student)
        django_session_key = _seed_django_session(student)

        result = track_service.archive_track(self.track.id, requesting_user=self.global_admin)

        self.assertEqual(result["msg"], "Track archived successfully")

        open_session.refresh_from_db()
        self.assertIsNotNone(open_session.revoked_at)
        self.assertIsNotNone(open_session.ended_at)

        self.assertFalse(
            Session.objects.filter(session_key=django_session_key).exists(),
            "Django session row should have been deleted on track archive",
        )

    # --- indirect via group membership ---

    def test_archive_revokes_sessions_for_active_group_members(self):
        # Indirect: user has no ``User.track`` but is in a group on this track.
        group = Groups.objects.create(group_name="G1", track=self.track)
        member = User.objects.create_user(
            email="member@example.com",
            first_name="Mia",
            last_name="Member",
            password="testpass",
        )
        GroupMembership.objects.create(
            group=group,
            user=member,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        open_session = UserSession.objects.create(user=member)
        django_session_key = _seed_django_session(member)

        track_service.archive_track(self.track.id, requesting_user=self.global_admin)

        open_session.refresh_from_db()
        self.assertIsNotNone(open_session.revoked_at)
        self.assertFalse(Session.objects.filter(session_key=django_session_key).exists())

    def test_archive_skips_users_who_already_left_the_group(self):
        # ``left_at`` is set → membership is no longer active → user should NOT
        # be logged out by this track's archival.
        group = Groups.objects.create(group_name="G1", track=self.track)
        former_member = User.objects.create_user(
            email="former@example.com",
            first_name="Fred",
            last_name="Former",
            password="testpass",
        )
        now = timezone.now()
        GroupMembership.objects.create(
            group=group,
            user=former_member,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            joined_at=now - timedelta(days=1),
            left_at=now,
        )
        open_session = UserSession.objects.create(user=former_member)
        django_session_key = _seed_django_session(former_member)

        track_service.archive_track(self.track.id, requesting_user=self.global_admin)

        open_session.refresh_from_db()
        self.assertIsNone(open_session.revoked_at)
        self.assertTrue(Session.objects.filter(session_key=django_session_key).exists())

    # --- isolation ---

    def test_archive_does_not_touch_users_on_other_tracks(self):
        bystander = User.objects.create_user(
            email="other@example.com",
            first_name="Olly",
            last_name="Other",
            track=self.other_track,
            password="testpass",
        )
        open_session = UserSession.objects.create(user=bystander)
        django_session_key = _seed_django_session(bystander)

        track_service.archive_track(self.track.id, requesting_user=self.global_admin)

        open_session.refresh_from_db()
        self.assertIsNone(open_session.revoked_at)
        self.assertTrue(Session.objects.filter(session_key=django_session_key).exists())

    # --- operational-admin exemption ---

    def test_archive_does_not_log_out_operational_admin_on_archived_track(self):
        # The login gate exempts operational admins from ``is_track_archived``,
        # so mid-session termination must mirror that — otherwise a track
        # admin archiving their own track would instantly lock themselves out.
        track_admin = User.objects.create_user(
            email="trackadmin@example.com",
            first_name="Tara",
            last_name="TrackAdmin",
            track=self.track,
            password="testpass",
        )
        AdminScope.objects.create(user=track_admin, track=self.track, is_global=False)
        open_session = UserSession.objects.create(user=track_admin)
        django_session_key = _seed_django_session(track_admin)

        track_service.archive_track(self.track.id, requesting_user=self.global_admin)

        open_session.refresh_from_db()
        self.assertIsNone(open_session.revoked_at)
        self.assertTrue(Session.objects.filter(session_key=django_session_key).exists())

    # --- guardrails ---

    def test_non_global_admin_cannot_archive_and_does_not_terminate_sessions(self):
        track_admin = User.objects.create_user(
            email="ta@example.com",
            first_name="T",
            last_name="A",
            password="testpass",
        )
        AdminScope.objects.create(user=track_admin, track=self.track, is_global=False)

        student = User.objects.create_user(
            email="student2@example.com",
            first_name="Sara",
            last_name="Student",
            track=self.track,
            password="testpass",
        )
        open_session = UserSession.objects.create(user=student)

        result = track_service.archive_track(self.track.id, requesting_user=track_admin)

        self.assertEqual(result["msg"], "Only global admins can archive tracks")
        self.track.refresh_from_db()
        self.assertFalse(self.track.is_archived)
        open_session.refresh_from_db()
        self.assertIsNone(open_session.revoked_at)

    def test_restore_track_does_not_resurrect_sessions(self):
        student = User.objects.create_user(
            email="student3@example.com",
            first_name="S",
            last_name="S",
            track=self.track,
            password="testpass",
        )
        UserSession.objects.create(user=student)

        track_service.archive_track(self.track.id, requesting_user=self.global_admin)
        restore_result = track_service.restore_track(self.track.id, requesting_user=self.global_admin)

        self.assertEqual(restore_result["msg"], "Track restored successfully")
        # Once revoked, sessions stay revoked — restoring a track does not
        # re-grant a user a session they no longer have. They must log in.
        revoked = UserSession.objects.filter(user=student, revoked_at__isnull=False).count()
        self.assertEqual(revoked, 1)
