"""Tests for the archived-track forced-logout flow introduced in PR #142.

Covers three layers:

1. ``apps.users.utils.sessions.terminate_user_sessions`` — the shared helper
   used by password reset and archived-track lockout. Was previously the
   private ``_terminate_all_sessions`` in ``auth_service``; this suite pins
   the contract now that the public helper has new callers.
2. ``apps.users.utils.track_gate.revoke_sessions_for_archived_track`` —
   iterates members of a track, exempts operational admins (matches the
   login-gate exemption so an admin who archives their own track doesn't
   kick themselves out mid-fix).
3. ``Tracks.save()`` override — fires the revocation via
   ``transaction.on_commit`` only on the False → True transition, so a
   rolled-back archive doesn't strand users in a logged-out state.

Run with: ``python manage.py test tests.apps.users.test_track_session_revocation``
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from apps.groups.models import Countries, CountryStates, Tracks
from apps.user_sessions.models import UserSession
from apps.users.models import AdminScope
from apps.users.utils.sessions import terminate_user_sessions
from apps.users.utils.track_gate import revoke_sessions_for_archived_track


User = get_user_model()


def _seed_django_session(user) -> str:
    """Create a real django_session row whose decoded data names ``user``.

    Mirrors what the auth backend writes after a successful login, so
    ``_flush_django_sessions_for_user`` has something realistic to scan.
    """
    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    store.create()
    return store.session_key


class TerminateUserSessionsTests(TestCase):
    """Pin the shared helper's contract: revokes open rows, leaves others
    alone, flushes django_session rows belonging to the target user."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="terminate-me@test.com",
            password="pw",
            first_name="T",
            last_name="U",
        )
        self.bystander = User.objects.create_user(
            email="bystander@test.com",
            password="pw",
            first_name="B",
            last_name="U",
        )

    def test_revokes_open_user_session_rows(self):
        open_row = UserSession.objects.create(user=self.user)

        before = timezone.now()
        terminate_user_sessions(self.user)

        open_row.refresh_from_db()
        self.assertIsNotNone(open_row.revoked_at)
        self.assertIsNotNone(open_row.ended_at)
        self.assertGreaterEqual(open_row.revoked_at, before)

    def test_leaves_other_users_sessions_alone(self):
        mine = UserSession.objects.create(user=self.user)
        theirs = UserSession.objects.create(user=self.bystander)

        terminate_user_sessions(self.user)

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertIsNotNone(mine.revoked_at)
        self.assertIsNone(theirs.revoked_at)
        self.assertIsNone(theirs.ended_at)

    def test_does_not_overwrite_already_revoked_timestamps(self):
        # The filter clause skips rows that already carry revoked_at/ended_at
        # so audit history (e.g. who was logged out by which event) survives.
        opened_at = timezone.now() - timedelta(hours=2)
        earlier_revoke = timezone.now() - timedelta(hours=1)
        already_revoked = UserSession.objects.create(
            user=self.user,
            created_at=opened_at,
            last_activity_at=opened_at,
            expires_at=opened_at + timedelta(hours=24),
            revoked_at=earlier_revoke,
            ended_at=earlier_revoke,
        )

        terminate_user_sessions(self.user)

        already_revoked.refresh_from_db()
        self.assertEqual(already_revoked.revoked_at, earlier_revoke)
        self.assertEqual(already_revoked.ended_at, earlier_revoke)

    def test_flushes_django_session_rows_for_user(self):
        my_sid = _seed_django_session(self.user)
        their_sid = _seed_django_session(self.bystander)

        terminate_user_sessions(self.user)

        self.assertFalse(Session.objects.filter(session_key=my_sid).exists())
        self.assertTrue(Session.objects.filter(session_key=their_sid).exists())


class RevokeSessionsForArchivedTrackTests(TestCase):
    """The track-archival callback iterates members, exempts admins, and
    delegates the per-user kill to ``terminate_user_sessions``."""

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="ARCHIVE-ME", state=state)
        self.other_track = Tracks.objects.create(
            track_name="UNTOUCHED", state=state,
        )

        # Track members:
        #  - admin_member: operational admin, must NOT be logged out
        #    (mirrors the login-gate exemption).
        #  - regular_member: must be logged out.
        #  - off_track_member: belongs to a different track, must be untouched.
        self.admin_member = User.objects.create_user(
            email="admin-on-track@test.com",
            password="pw",
            first_name="A",
            last_name="A",
            track=self.track,
        )
        AdminScope.objects.create(user=self.admin_member, is_global=True)

        self.regular_member = User.objects.create_user(
            email="member@test.com",
            password="pw",
            first_name="M",
            last_name="M",
            track=self.track,
        )
        self.off_track_member = User.objects.create_user(
            email="elsewhere@test.com",
            password="pw",
            first_name="E",
            last_name="E",
            track=self.other_track,
        )

    def test_revokes_regular_member_sessions(self):
        row = UserSession.objects.create(user=self.regular_member)

        count = revoke_sessions_for_archived_track(self.track)

        row.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertIsNotNone(row.revoked_at)
        self.assertIsNotNone(row.ended_at)

    def test_exempts_operational_admin_member(self):
        # The admin who archived the track (or any operational admin assigned
        # to the track) must keep their session — matches the login-gate
        # exemption so they can keep working through the archive operation.
        admin_row = UserSession.objects.create(user=self.admin_member)
        member_row = UserSession.objects.create(user=self.regular_member)

        revoke_sessions_for_archived_track(self.track)

        admin_row.refresh_from_db()
        member_row.refresh_from_db()
        self.assertIsNone(admin_row.revoked_at)
        self.assertIsNone(admin_row.ended_at)
        self.assertIsNotNone(member_row.revoked_at)

    def test_does_not_touch_users_in_other_tracks(self):
        off_row = UserSession.objects.create(user=self.off_track_member)

        revoke_sessions_for_archived_track(self.track)

        off_row.refresh_from_db()
        self.assertIsNone(off_row.revoked_at)
        self.assertIsNone(off_row.ended_at)

    def test_returns_count_of_non_admin_members_processed(self):
        # 1 regular member, 1 admin exempted; count reflects non-admins.
        count = revoke_sessions_for_archived_track(self.track)
        self.assertEqual(count, 1)


class TracksSaveArchiveTransitionTests(TestCase):
    """The save() override should only schedule revocation on the False →
    True transition, and only after the surrounding transaction commits."""

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRANS-1", state=state)
        self.member = User.objects.create_user(
            email="transition@test.com",
            password="pw",
            first_name="T",
            last_name="M",
            track=self.track,
        )

    def test_first_create_archived_does_not_revoke(self):
        # A brand-new archived track has no prior False state and no members
        # whose sessions should be killed; the override must not fire.
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Tracks.objects.create(
                track_name="BORN-ARCHIVED",
                state=self.track.state,
                is_archived=True,
            )
        self.assertEqual(callbacks, [])

    def test_false_to_true_transition_revokes_on_commit(self):
        open_row = UserSession.objects.create(user=self.member)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.track.is_archived = True
            self.track.save(update_fields=["is_archived"])

        # Exactly one on_commit callback was scheduled, and it fired.
        self.assertEqual(len(callbacks), 1)
        open_row.refresh_from_db()
        self.assertIsNotNone(open_row.revoked_at)
        self.assertIsNotNone(open_row.ended_at)

    def test_idempotent_save_when_already_archived(self):
        # Initial archive should fire the callback once and only once.
        self.track.is_archived = True
        self.track.save(update_fields=["is_archived"])

        open_row = UserSession.objects.create(user=self.member)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            # Re-saving an already-archived track must not schedule another
            # revocation; otherwise any unrelated edit to an archived track
            # would re-kill freshly-issued admin reset sessions.
            self.track.save(update_fields=["is_archived"])

        self.assertEqual(callbacks, [])
        open_row.refresh_from_db()
        self.assertIsNone(open_row.revoked_at)

    def test_unarchive_does_not_revoke(self):
        # Restoring a track must not log anyone out — opposite direction.
        self.track.is_archived = True
        self.track.save(update_fields=["is_archived"])

        open_row = UserSession.objects.create(user=self.member)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.track.is_archived = False
            self.track.save(update_fields=["is_archived"])

        self.assertEqual(callbacks, [])
        open_row.refresh_from_db()
        self.assertIsNone(open_row.revoked_at)

    def test_rolled_back_archive_does_not_strand_users(self):
        # The whole point of using transaction.on_commit: if the surrounding
        # atomic block raises, the revocation must NOT happen — otherwise an
        # admin gets the "archive failed" error AND their members lose their
        # sessions, which is exactly the stranded-state the PR prevents.
        open_row = UserSession.objects.create(user=self.member)

        class _Boom(Exception):
            pass

        with self.assertRaises(_Boom):
            with transaction.atomic():
                self.track.is_archived = True
                self.track.save(update_fields=["is_archived"])
                raise _Boom()

        open_row.refresh_from_db()
        self.assertIsNone(open_row.revoked_at)
        self.assertIsNone(open_row.ended_at)
        # And the archive itself rolled back.
        self.track.refresh_from_db()
        self.assertFalse(self.track.is_archived)
