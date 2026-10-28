"""The mentor replacement notifications, actually rendered and sent.

The service tests mock ``send_system_email``, which proves the right call is
made but nothing about the templates: a missing merge tag or broken Django
syntax would pass there and fail in production. These drive the real path and
read what lands in the outbox.
"""
from django.core import mail
from django.test import TestCase

from apps.admin.services.mentor_match import replace_mentor
from apps.groups.models import Groups, GroupMembership
from apps.services.models import SystemEmailTemplate
from apps.users.models import MentorProfile, User

MENTOR = GroupMembership.MembershipRoleChoices.MENTOR


class MentorReplacementEmailTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="BTF01")
        self.departing = self._mentor("helen@test.local", "Helen", "Marsh")
        self.incoming = self._mentor("samuel@test.local", "Samuel", "Adeyemi")
        self.membership = GroupMembership.objects.create(
            user=self.departing, group=self.group, membership_role=MENTOR,
        )

    def _mentor(self, email, first, last):
        user = User.objects.create_user(
            email=email, first_name=first, last_name=last, password="testpass",
        )
        MentorProfile.objects.create(
            user=user, institution="USYD", mentor_reason="Testing", max_group_count=3,
        )
        return user

    def _replace(self, **extra):
        replace_mentor({
            "membershipId": self.membership.id,
            "groupId": self.group.id,
            "newMentorUserId": self.incoming.id,
            **extra,
        })

    def test_both_emails_render_and_reach_the_right_mentor(self):
        self._replace()

        by_recipient = {message.to[0]: message for message in mail.outbox}
        self.assertCountEqual(by_recipient, [self.departing.email, self.incoming.email])

        departing = by_recipient[self.departing.email]
        self.assertIn("BTF01", departing.subject)
        self.assertIn("Helen", departing.body)
        # The group name is merged into the body, not left as a raw tag.
        self.assertIn("BTF01", departing.body)
        self.assertNotIn("{{", departing.body)

        incoming = by_recipient[self.incoming.email]
        self.assertIn("BTF01", incoming.subject)
        self.assertIn("Samuel", incoming.body)
        self.assertNotIn("{{", incoming.body)

    def test_the_html_alternative_is_attached_and_merged(self):
        self._replace()

        message = next(m for m in mail.outbox if m.to == [self.incoming.email])
        html = next(body for body, mime in message.alternatives if mime == "text/html")
        self.assertIn("Samuel", html)
        self.assertIn("BTF01", html)
        self.assertNotIn("{{", html)

    def test_an_admin_edit_replaces_the_default_wording(self):
        SystemEmailTemplate.objects.create(
            key="mentor_assigned",
            subject="You now mentor {{ group_name }}",
            body_html="<p>Hi {{ mentor_first_name }}, welcome to {{ group_name }}.</p>",
        )

        self._replace()

        message = next(m for m in mail.outbox if m.to == [self.incoming.email])
        self.assertEqual(message.subject, "You now mentor BTF01")
        self.assertIn("welcome to BTF01", message.body)

    def test_unticking_a_box_sends_only_the_other_email(self):
        self._replace(notifyDeparting=False)

        self.assertEqual([m.to[0] for m in mail.outbox], [self.incoming.email])

    def test_re_picking_the_sitting_mentor_sends_nothing(self):
        replace_mentor({
            "membershipId": self.membership.id,
            "groupId": self.group.id,
            "newMentorUserId": self.departing.id,
        })

        self.assertEqual(mail.outbox, [])
