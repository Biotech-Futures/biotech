"""Tests for admin mentor service."""
from django.test import TestCase
from django.utils import timezone

from apps.admin.services.mentor import get_mentor_list, set_mentor_active
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.users.models import MentorProfile, User
from apps.users.models.admin_scope import AdminScope


class MentorServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-1", state=self.state)
        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)
        self.mentor = User.objects.create_user(
            email="mentor1@example.com",
            first_name="Mina",
            last_name="Mentor",
            track=self.track,
            password="testpass",
            is_active=True,
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="UNSW",
            mentor_reason="Testing",
            max_group_count=3,
            background="Science",
        )

    def test_get_mentor_list_returns_empty_when_no_mentors(self):
        MentorProfile.objects.all().delete()
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_mentor_list_returns_mentor_dict(self):
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        mentor = result[0]
        self.assertEqual(mentor["firstName"], "Mina")
        self.assertEqual(mentor["lastName"], "Mentor")
        self.assertEqual(mentor["email"], "mentor1@example.com")
        self.assertEqual(mentor["institution"], "UNSW")
        self.assertEqual(mentor["trackCode"], "TRACK-1")
        self.assertEqual(mentor["maxGroupCount"], 3)
        self.assertEqual(mentor["currentAssignedCount"], 0)
        self.assertEqual(mentor["remainingCapacity"], 3)
        self.assertTrue(mentor["isActive"])

    def test_get_mentor_list_counts_assigned_groups(self):
        group = Groups.objects.create(group_name="Group A", track=self.track)
        GroupMembership.objects.create(
            user=self.mentor,
            group=group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(result[0]["currentAssignedCount"], 1)
        self.assertEqual(result[0]["remainingCapacity"], 2)

    def test_get_mentor_list_excludes_mentors_in_archived_tracks(self):
        archived_track = Tracks.objects.create(track_name="ARCHIVED", state=self.state)
        archived_track.is_archived = True
        archived_track.save()
        archived_mentor = User.objects.create_user(
            email="archived-mentor@example.com", first_name="Archived",
            last_name="Mentor", track=archived_track, password="testpass",
        )
        MentorProfile.objects.create(
            user=archived_mentor, institution="UAT", mentor_reason="Test",
        )
        result = get_mentor_list(requesting_user=self.admin_user)
        emails = [m["email"] for m in result]
        self.assertIn("mentor1@example.com", emails)
        self.assertNotIn("archived-mentor@example.com", emails)

    def test_set_mentor_active_deactivates(self):
        set_mentor_active(self.mentor.id, False)
        self.mentor.refresh_from_db()
        self.assertFalse(self.mentor.is_active)

    def test_set_mentor_active_activates(self):
        self.mentor.is_active = False
        self.mentor.save()
        set_mentor_active(self.mentor.id, True)
        self.mentor.refresh_from_db()
        self.assertTrue(self.mentor.is_active)
