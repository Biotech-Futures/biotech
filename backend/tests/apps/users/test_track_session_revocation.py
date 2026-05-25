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

from apps.admin.services import track as track_service
from apps.groups.models import (
    Countries,
    CountryStates,
    GroupMembership,
    Groups,
    Tracks,
)
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

    def test_revokes_users_in_active_group_membership_on_track(self):
        # Indirect membership: ``User.track`` points elsewhere (or is null)
        # but the user is in a group that lives on the archived track.
        # The login gate alone misses this population, so a mentor whose
        # primary track is X but who actively collaborates in a group on
        # track Y (now archived) would otherwise keep their session.
        group_on_track = Groups.objects.create(
            group_name="GroupOnArchivedTrack", track=self.track,
        )
        cross_track_member = User.objects.create_user(
            email="cross-track@test.com",
            password="pw",
            first_name="C",
            last_name="X",
            track=self.other_track,
        )
        GroupMembership.objects.create(
            group=group_on_track,
            user=cross_track_member,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        row = UserSession.objects.create(user=cross_track_member)

        count = revoke_sessions_for_archived_track(self.track)

        row.refresh_from_db()
        self.assertIsNotNone(row.revoked_at)
        self.assertIsNotNone(row.ended_at)
        # 2 non-admins: setUp's regular_member (direct ``User.track``) plus
        # this cross_track_member (active group membership). The count is
        # users-processed, not rows-revoked, so it doesn't depend on whether
        # regular_member happens to have an open UserSession row.
        self.assertEqual(count, 2)

    def test_skips_users_whose_group_membership_was_left(self):
        # ``left_at`` set ⇒ membership is no longer active ⇒ user is not in
        # the affected set even though the GroupMembership row still exists
        # in the table for audit history.
        group_on_track = Groups.objects.create(
            group_name="ArchiveGroup", track=self.track,
        )
        former_member = User.objects.create_user(
            email="former@test.com",
            password="pw",
            first_name="F",
            last_name="M",
            track=self.other_track,
        )
        now = timezone.now()
        GroupMembership.objects.create(
            group=group_on_track,
            user=former_member,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            joined_at=now - timedelta(days=2),
            left_at=now - timedelta(days=1),
        )
        row = UserSession.objects.create(user=former_member)

        revoke_sessions_for_archived_track(self.track)

        row.refresh_from_db()
        self.assertIsNone(row.revoked_at)
        self.assertIsNone(row.ended_at)

    def test_dedupes_user_in_both_direct_and_group_membership(self):
        # A user who is BOTH on the archived track directly AND in a group on
        # the same archived track must not be processed twice by the OR
        # union — would double-count terminations in the ops log.
        group_on_track = Groups.objects.create(
            group_name="DupeGroup", track=self.track,
        )
        GroupMembership.objects.create(
            group=group_on_track,
            user=self.regular_member,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        UserSession.objects.create(user=self.regular_member)

        count = revoke_sessions_for_archived_track(self.track)

        self.assertEqual(count, 1)

    def test_emits_ops_log_with_terminated_and_skipped_counts(self):
        # Ops needs to be able to answer "how many sessions did that archive
        # kill, and how many admins were spared" without grepping every per-
        # user terminate call. One structured log event per archive.
        UserSession.objects.create(user=self.regular_member)
        UserSession.objects.create(user=self.admin_member)

        with self.assertLogs("apps.users.utils.track_gate", level="INFO") as cap:
            revoke_sessions_for_archived_track(self.track)

        matching = [r for r in cap.records if "track.archive" in r.getMessage()]
        self.assertEqual(len(matching), 1)
        record = matching[0]
        self.assertEqual(record.terminated_user_count, 1)
        self.assertEqual(record.skipped_admin_count, 1)
        self.assertEqual(record.track_id, self.track.id)


class ArchiveTrackEndToEndTests(TestCase):
    """End-to-end coverage of the public admin entry point ``archive_track``.

    PR #142 routes the revocation through ``Tracks.save()`` + on_commit so
    every code path that flips ``is_archived`` is covered, including the
    admin service. These tests pin the integration: calling the public
    service from an admin view boots affected users out, while
    ``restore_track`` does NOT resurrect anyone's session.
    """

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="E2E-ARCHIVE", state=state)

        self.global_admin = User.objects.create_user(
            email="global-admin@test.com",
            password="pw",
            first_name="G",
            last_name="A",
        )
        AdminScope.objects.create(user=self.global_admin, is_global=True)

        self.student = User.objects.create_user(
            email="e2e-student@test.com",
            password="pw",
            first_name="E",
            last_name="S",
            track=self.track,
        )

    def test_archive_track_service_call_terminates_member_sessions(self):
        row = UserSession.objects.create(user=self.student)
        sid = _seed_django_session(self.student)

        with self.captureOnCommitCallbacks(execute=True):
            result = track_service.archive_track(
                self.track.id, requesting_user=self.global_admin,
            )

        self.assertEqual(result["msg"], "Track archived successfully")
        row.refresh_from_db()
        self.assertIsNotNone(row.revoked_at)
        self.assertFalse(Session.objects.filter(session_key=sid).exists())

    def test_non_global_admin_archive_attempt_does_not_terminate(self):
        # Permission guard fires before save(); the override never runs.
        scoped_admin = User.objects.create_user(
            email="scoped-admin@test.com",
            password="pw",
            first_name="S",
            last_name="A",
            track=self.track,
        )
        AdminScope.objects.create(
            user=scoped_admin, track=self.track, is_global=False,
        )
        row = UserSession.objects.create(user=self.student)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = track_service.archive_track(
                self.track.id, requesting_user=scoped_admin,
            )

        self.assertEqual(result["msg"], "Only global admins can archive tracks")
        self.track.refresh_from_db()
        self.assertFalse(self.track.is_archived)
        self.assertEqual(callbacks, [])
        row.refresh_from_db()
        self.assertIsNone(row.revoked_at)

    def test_restore_track_does_not_resurrect_revoked_sessions(self):
        # Once a session is revoked, restoring the track must NOT undo the
        # revocation — the user must re-authenticate. Otherwise an admin
        # who archived a track in error could un-archive it and silently
        # hand every kicked-out user their old session back.
        UserSession.objects.create(user=self.student)

        with self.captureOnCommitCallbacks(execute=True):
            track_service.archive_track(
                self.track.id, requesting_user=self.global_admin,
            )

        revoked_before_restore = UserSession.objects.filter(
            user=self.student, revoked_at__isnull=False,
        ).count()

        with self.captureOnCommitCallbacks(execute=True) as restore_callbacks:
            restore_result = track_service.restore_track(
                self.track.id, requesting_user=self.global_admin,
            )

        self.assertEqual(restore_result["msg"], "Track restored successfully")
        # restore must not schedule any revocation callback (it's the
        # opposite transition) and must leave the old revoked_at intact.
        self.assertEqual(restore_callbacks, [])
        self.assertEqual(
            UserSession.objects.filter(
                user=self.student, revoked_at__isnull=False,
            ).count(),
            revoked_before_restore,
        )


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
