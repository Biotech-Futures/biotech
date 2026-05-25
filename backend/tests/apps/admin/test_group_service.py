from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.admin.services.group import query_group_messages, query_groups
from apps.chat.models import Messages
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.users.models import MentorProfile, User


class AdminGroupServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-1", state=state)
        self.group = Groups.objects.create(group_name="Group One", track=self.track)
        self.mentor = User.objects.create_user(
            email="mentor@example.com",
            first_name="Mina",
            last_name="Mentor",
            track=self.track,
            password="testpass",
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="UNSW",
            mentor_reason="Testing",
        )
        self.membership = GroupMembership.objects.create(
            group=self.group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

    def test_query_groups_uses_adminweb_camel_case_contract(self):
        result = query_groups()
        group = result["data"]["items"][0]

        self.assertIn("createdAt", group)
        self.assertIn("updatedAt", group)
        self.assertNotIn("created_at", group)
        self.assertEqual(group["mentor"]["membershipId"], self.membership.id)
        self.assertNotIn("membership_id", group["mentor"])

    def test_query_groups_orders_by_created_at_desc(self):
        older = self.group
        newer = Groups.objects.create(group_name="Group Two", track=self.track)

        now = timezone.now()
        Groups.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Groups.objects.filter(id=newer.id).update(created_at=now)

        result = query_groups(limit=10)

        self.assertEqual(
            [group["id"] for group in result["data"]["items"]],
            [str(newer.id), str(older.id)],
        )

    def test_query_group_messages_handles_removed_gif_relation(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="Hello from the admin history endpoint",
        )

        result = query_group_messages(str(self.group.id))

        self.assertEqual(result["msg"], "Group messages retrieved successfully")
        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["id"], str(message.id))
        self.assertIsNone(result["data"]["items"][0]["gif"])
