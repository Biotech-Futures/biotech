"""AM8: a mentor may take a student's message down, and nothing more.

The rule is deliberately narrow, so each boundary gets its own test:

* only in a group the user actually mentors,
* only against a message a *student* of that group sent,
* delete only - never edit, never restore.

Membership role is what counts here, not a role assignment elsewhere in the
system: mentoring one group is not a licence to moderate another.
"""
import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.chat.models import MessageAttachment, Messages
from apps.groups.models import Groups, GroupMembership
from apps.users.models.admin_scope import AdminScope

STUDENT = GroupMembership.MembershipRoleChoices.STUDENT
MENTOR = GroupMembership.MembershipRoleChoices.MENTOR


class MentorMessageModerationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(email="s@test.com", password="pw")
        self.mentor = User.objects.create_user(email="m@test.com", password="pw")
        self.other_mentor = User.objects.create_user(email="m2@test.com", password="pw")
        self.outsider_mentor = User.objects.create_user(email="m3@test.com", password="pw")
        self.admin = User.objects.create_user(email="a@test.com", password="pw")
        AdminScope.objects.create(user=self.admin)

        self.group = Groups.objects.create(group_name="G1")
        GroupMembership.objects.create(user=self.student, group=self.group, membership_role=STUDENT)
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role=MENTOR)
        GroupMembership.objects.create(user=self.other_mentor, group=self.group, membership_role=MENTOR)

        # Mentors a different group entirely.
        self.elsewhere = Groups.objects.create(group_name="G2")
        GroupMembership.objects.create(
            user=self.outsider_mentor, group=self.elsewhere, membership_role=MENTOR,
        )

        self.client_mentor = APIClient()
        self.client_mentor.force_authenticate(user=self.mentor)
        self.client_outsider = APIClient()
        self.client_outsider.force_authenticate(user=self.outsider_mentor)

    def _detail_url(self, message, group=None):
        return reverse(
            "group-messages-detail",
            kwargs={"group_pk": (group or self.group).id, "pk": message.id},
        )

    def _message_from(self, sender, group=None):
        return Messages.objects.create(
            group=group or self.group, sender_user=sender, message_text="said something",
        )

    # --- what a mentor may do ------------------------------------------------

    def test_mentor_soft_deletes_a_students_message(self):
        message = self._message_from(self.student)

        response = self.client_mentor.delete(self._detail_url(message))

        self.assertEqual(response.status_code, 204)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.deleted_by_id, self.mentor.id)
        # Soft, not gone: the row and its text survive for an admin to review.
        self.assertEqual(message.message_text, "said something")

    def test_the_removal_is_audit_logged(self):
        message = self._message_from(self.student)

        self.client_mentor.delete(self._detail_url(message))

        entry = AuditLog.objects.filter(
            entity_type="message", entity_id=message.id, action="delete",
        ).first()
        self.assertIsNotNone(entry, "a moderation action must leave an audit trail")
        self.assertEqual(entry.actor_user_id, self.mentor.id)

    # --- and what it must not extend to --------------------------------------

    def test_mentor_cannot_edit_the_message_it_can_delete(self):
        message = self._message_from(self.student)

        response = self.client_mentor.patch(
            self._detail_url(message), {"message_text": "rewritten"}, format="json",
        )

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertEqual(message.message_text, "said something")

    def test_mentor_restores_what_it_removed_itself(self):
        message = self._message_from(self.student)
        self.client_mentor.delete(self._detail_url(message))

        response = self.client_mentor.post(f"{self._detail_url(message)}restore/")

        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)
        self.assertIsNone(message.deleted_by_id)

    def test_mentor_cannot_restore_another_mentors_removal(self):
        message = self._message_from(self.student)
        other = APIClient()
        other.force_authenticate(user=self.other_mentor)
        other.delete(self._detail_url(message))

        response = self.client_mentor.post(f"{self._detail_url(message)}restore/")

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)

    def test_mentor_cannot_restore_an_admins_removal(self):
        message = self._message_from(self.student)
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin)
        admin_client.delete(self._detail_url(message))

        response = self.client_mentor.post(f"{self._detail_url(message)}restore/")

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)

    def test_mentor_reads_back_only_the_text_it_removed(self):
        mine = self._message_from(self.student)
        theirs = self._message_from(self.student)
        self.client_mentor.delete(self._detail_url(mine))
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin)
        admin_client.delete(self._detail_url(theirs))

        listed = self.client_mentor.get(
            reverse("group-messages-list", kwargs={"group_pk": self.group.id})
        ).json()["items"]
        by_id = {str(item["id"]): item for item in listed}

        self.assertEqual(by_id[str(mine.id)]["message_text"], "said something")
        # Someone else's removal stays a blank tombstone for this mentor.
        self.assertEqual(by_id[str(theirs.id)]["message_text"], "")

    def test_mentor_of_another_group_is_refused(self):
        message = self._message_from(self.student)

        response = self.client_outsider.delete(self._detail_url(message))

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

    def test_mentor_cannot_delete_another_mentors_message(self):
        message = self._message_from(self.other_mentor)

        response = self.client_mentor.delete(self._detail_url(message))

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

    def test_mentor_cannot_delete_an_admins_message(self):
        # The admin posts without being a group member, so they are not a
        # student of this group and the mentor rule does not reach them.
        message = self._message_from(self.admin)

        response = self.client_mentor.delete(self._detail_url(message))

        self.assertEqual(response.status_code, 403)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

class RemovedMessageContentTests(TestCase):
    """AM8: moderation reviews what was removed without restoring it first.

    The text was already kept for them. An image is the thing most worth
    looking at before deciding, so it is kept on the same terms - and nobody
    else's view changes.
    """

    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(email="rs@test.com", password="pw")
        self.other_student = User.objects.create_user(email="rs2@test.com", password="pw")
        self.mentor = User.objects.create_user(email="rm@test.com", password="pw")
        self.admin = User.objects.create_user(email="ra@test.com", password="pw")
        AdminScope.objects.create(user=self.admin)

        self.group = Groups.objects.create(group_name="RG")
        for user, role in (
            (self.student, STUDENT),
            (self.other_student, STUDENT),
            (self.mentor, MENTOR),
        ):
            GroupMembership.objects.create(user=user, group=self.group, membership_role=role)

        self.message = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="look at this",
        )
        self.attachment = MessageAttachment.objects.create(
            message=self.message,
            storage_key="chat/removed.png",
            attachment_filename="removed.png",
            attachment_mime_type="image/png",
            attachment_size=1234,
        )
        self.message.soft_delete(self.mentor)

        self.as_admin = APIClient()
        self.as_admin.force_authenticate(user=self.admin)
        self.as_mentor = APIClient()
        self.as_mentor.force_authenticate(user=self.mentor)
        self.as_peer = APIClient()
        self.as_peer.force_authenticate(user=self.other_student)

    def _listed(self, client):
        url = reverse("group-messages-list", kwargs={"group_pk": self.group.id})
        response = client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        return {item["id"]: item for item in response.data["items"]}[self.message.id]

    def _download_url(self):
        return reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": self.group.id,
                "pk": self.message.id,
                "attachment_pk": self.attachment.id,
            },
        )

    def test_an_admin_sees_the_removed_attachment_without_restoring(self):
        item = self._listed(self.as_admin)

        self.assertTrue(item["is_deleted"])
        self.assertEqual(item["message_text"], "look at this")
        self.assertEqual(
            [a["attachment_filename"] for a in item["attachments"]], ["removed.png"],
        )

    def test_the_mentor_who_removed_it_sees_it_too(self):
        item = self._listed(self.as_mentor)

        self.assertEqual([a["attachment_filename"] for a in item["attachments"]], ["removed.png"])

    def test_another_member_still_sees_a_blank_tombstone(self):
        item = self._listed(self.as_peer)

        self.assertTrue(item["is_deleted"])
        self.assertEqual(item["message_text"], "")
        self.assertEqual(item["attachments"], [])

    # The fixture's storage_key points at nothing, so a permitted download
    # still ends in 404 - from the storage lookup, not the permission check.
    # The two are told apart by their message.
    HIDDEN = "Attachment not found for this message."

    def _detail(self, response):
        """The refusal reason, whichever response class produced it.

        A permitted request falls through to the storage layer, which answers
        with a plain JsonResponse rather than a DRF one.
        """
        try:
            return json.loads(response.content).get("detail")
        except (ValueError, AttributeError):
            return None

    def test_an_admin_gets_past_the_permission_check(self):
        # Before this the message was outside the download's queryset, so even
        # the admin panel - which does list the attachment - could not open it.
        response = self.as_admin.get(self._download_url())

        self.assertNotEqual(self._detail(response), self.HIDDEN)

    def test_the_mentor_who_removed_it_gets_past_it_too(self):
        response = self.as_mentor.get(self._download_url())

        self.assertNotEqual(self._detail(response), self.HIDDEN)

    def test_another_member_is_refused(self):
        response = self.as_peer.get(self._download_url())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._detail(response), self.HIDDEN)


class SenderIdentityContractTests(TestCase):
    """A mentor may remove a *student's* message, so the client has to be able
    to tell whose a message is. That needs the sender's id, which the public
    payload omitted - leaving the UI unable to offer the action at all.
    """

    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(email="sc-s@test.com", password="pw")
        self.mentor = User.objects.create_user(email="sc-m@test.com", password="pw")
        self.admin = User.objects.create_user(email="sc-a@test.com", password="pw")
        AdminScope.objects.create(user=self.admin)

        self.group = Groups.objects.create(group_name="SC")
        GroupMembership.objects.create(user=self.student, group=self.group, membership_role=STUDENT)
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role=MENTOR)

        self.from_student = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="mine",
        )
        self.as_administrator = Messages.objects.create(
            group=self.group, sender_user=self.admin, message_text="notice",
            sent_as_admin=True,
        )

        self.as_mentor = APIClient()
        self.as_mentor.force_authenticate(user=self.mentor)
        self.as_admin = APIClient()
        self.as_admin.force_authenticate(user=self.admin)

    def _items(self, client):
        url = reverse("group-messages-list", kwargs={"group_pk": self.group.id})
        response = client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        return {item["id"]: item for item in response.data["items"]}

    def test_a_mentor_can_tell_a_students_message_by_its_sender(self):
        item = self._items(self.as_mentor)[self.from_student.id]

        self.assertEqual(item["sender_user"], self.student.id)

    def test_an_administrator_message_keeps_its_sender_hidden(self):
        # AM6: posting as "Administrator" must not be traceable to the person,
        # and the id would out them just as surely as the name.
        item = self._items(self.as_mentor)[self.as_administrator.id]

        self.assertIsNone(item["sender_user"])
        self.assertEqual(item["sender_name"], "Administrator")

    def test_an_admin_still_sees_who_really_sent_it(self):
        item = self._items(self.as_admin)[self.as_administrator.id]

        self.assertEqual(item["sender_user"], self.admin.id)
