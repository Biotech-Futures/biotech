"""
Tests for engagement-aware inactive mentor detection in
``bulk_replace_inactive_mentors``.

A mentor is "effectively inactive" when either:
  - their account ``is_active`` flag is False, OR
  - they have not sent a non-deleted chat message within the configured
    engagement window (default 30 days; mentors who have never messaged
    also fall into this bucket).
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.mentor_match import (
    DEFAULT_INACTIVE_DAYS,
    bulk_replace_inactive_mentors,
    get_inactive_mentor_membership_ids,
)
from apps.chat.models import Messages
from apps.groups.models import (
    Countries,
    CountryStates,
    Groups,
    GroupMembership,
    Tracks,
)
from apps.users.models import MentorProfile, User
from apps.users.models.admin_scope import AdminScope


def _make_mentor(email: str, track, *, is_active: bool = True) -> User:
    user = User.objects.create_user(
        email=email,
        first_name="Mina",
        last_name="Mentor",
        track=track,
        password="testpass",
    )
    if not is_active:
        # ``User.save`` reconciles is_active with account_status, so the
        # account_status enum is the authoritative way to deactivate.
        user.deactivate()
    MentorProfile.objects.create(
        user=user,
        institution="UNSW",
        mentor_reason="Testing",
        max_group_count=3,
    )
    return user


def _assign(mentor: User, group: Groups) -> GroupMembership:
    return GroupMembership.objects.create(
        group=group,
        user=mentor,
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
    )


def _send_message(mentor: User, group: Groups, sent_at, deleted: bool = False) -> Messages:
    return Messages.objects.create(
        sender_user=mentor,
        group=group,
        message_text="hello",
        sent_at=sent_at,
        deleted_at=sent_at if deleted else None,
    )


class BulkReplaceInactiveMentorsTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)

        self.engaged_mentor = _make_mentor("engaged@example.com", self.track)
        self.quiet_mentor = _make_mentor("quiet@example.com", self.track)
        self.never_messaged_mentor = _make_mentor("silent@example.com", self.track)
        self.deactivated_mentor = _make_mentor(
            "deactivated@example.com", self.track, is_active=False,
        )

        self.group_engaged = Groups.objects.create(group_name="G-eng", track=self.track)
        self.group_quiet = Groups.objects.create(group_name="G-quiet", track=self.track)
        self.group_silent = Groups.objects.create(group_name="G-silent", track=self.track)
        self.group_deactivated = Groups.objects.create(
            group_name="G-deact", track=self.track,
        )

        self.membership_engaged = _assign(self.engaged_mentor, self.group_engaged)
        self.membership_quiet = _assign(self.quiet_mentor, self.group_quiet)
        self.membership_silent = _assign(self.never_messaged_mentor, self.group_silent)
        self.membership_deactivated = _assign(
            self.deactivated_mentor, self.group_deactivated,
        )

        now = timezone.now()
        _send_message(self.engaged_mentor, self.group_engaged, now - timedelta(days=2))
        _send_message(self.quiet_mentor, self.group_quiet, now - timedelta(days=120))

    def test_detects_quiet_mentor_beyond_threshold(self):
        ids = get_inactive_mentor_membership_ids(30)
        self.assertIn(self.membership_quiet.id, ids)
        self.assertNotIn(self.membership_engaged.id, ids)

    def test_detects_mentor_who_never_messaged(self):
        ids = get_inactive_mentor_membership_ids(30)
        self.assertIn(self.membership_silent.id, ids)

    def test_detects_deactivated_mentor_regardless_of_messages(self):
        # Even with a fresh message, an is_active=False mentor must be flagged.
        _send_message(
            self.deactivated_mentor,
            self.group_deactivated,
            timezone.now() - timedelta(hours=1),
        )
        ids = get_inactive_mentor_membership_ids(30)
        self.assertIn(self.membership_deactivated.id, ids)

    def test_deleted_messages_do_not_count_as_engagement(self):
        # Replace the quiet mentor's stale message with a recent but deleted one.
        Messages.objects.filter(sender_user=self.quiet_mentor).delete()
        _send_message(
            self.quiet_mentor,
            self.group_quiet,
            timezone.now() - timedelta(hours=1),
            deleted=True,
        )
        ids = get_inactive_mentor_membership_ids(30)
        self.assertIn(self.membership_quiet.id, ids)

    def test_bulk_replace_clears_inactive_memberships(self):
        result = bulk_replace_inactive_mentors(30)

        # All three inactive memberships should be cleared.
        self.assertEqual(result["removedCount"], 3)
        self.assertEqual(result["inactiveDays"], 30)

        cleared_ids = {
            self.membership_quiet.id,
            self.membership_silent.id,
            self.membership_deactivated.id,
        }
        cleared = GroupMembership.objects.filter(id__in=cleared_ids)
        for membership in cleared:
            self.assertIsNotNone(membership.left_at)

        # The engaged mentor's membership stays intact.
        self.membership_engaged.refresh_from_db()
        self.assertIsNone(self.membership_engaged.left_at)

    def test_threshold_window_is_respected(self):
        # With a 200-day threshold, the quiet mentor (120 days stale) becomes
        # engaged again, so they should NOT be cleared.
        result = bulk_replace_inactive_mentors(200)
        self.membership_quiet.refresh_from_db()
        self.assertIsNone(self.membership_quiet.left_at)
        # The silent and deactivated mentors still get swept.
        self.assertEqual(result["removedCount"], 2)
        self.assertEqual(result["inactiveDays"], 200)

    def test_invalid_threshold_falls_back_to_default(self):
        result = bulk_replace_inactive_mentors("not-a-number")
        self.assertEqual(result["inactiveDays"], DEFAULT_INACTIVE_DAYS)

    def test_threshold_below_one_falls_back_to_default(self):
        result = bulk_replace_inactive_mentors(0)
        self.assertEqual(result["inactiveDays"], DEFAULT_INACTIVE_DAYS)


class BulkReplaceInactiveViewValidationTests(TestCase):
    """
    HTTP-layer validation for ``POST /api/v1/admin/mentor-match/bulk-replace-inactive``.

    The endpoint must STRICTLY accept JSON integers for ``inactiveDays`` —
    floats (even integer-valued ones like ``3.0``), strings, and booleans
    are all rejected with 400 instead of being silently coerced.
    """

    URL = "/api/v1/admin/mentor-match/bulk-replace-inactive/"

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        Tracks.objects.create(track_name="AUS-NSW", state=state)

        self.admin = User.objects.create_user(
            email="bulk-replace-admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin, is_global=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_missing_body_uses_default_window(self):
        response = self.client.post(self.URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["inactiveDays"], DEFAULT_INACTIVE_DAYS)

    def test_integer_value_accepted(self):
        response = self.client.post(self.URL, {"inactiveDays": 14}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["inactiveDays"], 14)

    def test_float_with_fractional_part_rejected(self):
        response = self.client.post(self.URL, {"inactiveDays": 3.14159}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_half_value_rejected(self):
        response = self.client.post(self.URL, {"inactiveDays": 3.5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_integer_valued_float_rejected(self):
        # 3.0 is still a float in JSON / Python — strict policy rejects it.
        response = self.client.post(self.URL, {"inactiveDays": 3.0}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_string_value_rejected(self):
        response = self.client.post(self.URL, {"inactiveDays": "30"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_non_numeric_string_rejected(self):
        response = self.client.post(self.URL, {"inactiveDays": "soon"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_boolean_rejected(self):
        # bool is a subclass of int in Python; we still reject it.
        response = self.client.post(self.URL, {"inactiveDays": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be an integer")

    def test_zero_rejected_as_below_minimum(self):
        response = self.client.post(self.URL, {"inactiveDays": 0}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be at least 1")

    def test_negative_integer_rejected_as_below_minimum(self):
        response = self.client.post(self.URL, {"inactiveDays": -5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "inactiveDays must be at least 1")
