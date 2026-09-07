from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketChannel,
    TicketMessage,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import lifecycle

User = get_user_model()


class SupportScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="agent@example.com", password="pass1234")

    def test_a_second_row_for_the_same_user_is_rejected(self):
        SupportScope.objects.create(user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupportScope.objects.create(user=self.user)

    def test_table_name_matches_the_admin_scope_convention(self):
        self.assertEqual(SupportScope._meta.db_table, "support_scope")


class TicketDefaultsTests(TestCase):
    def _ticket(self, **overrides):
        payload = {
            "ticket_number": "SUP-2026-00001",
            "subject": "Cannot access group workspace",
            "body": "I get an error opening my group.",
            "category": TicketCategory.HELP_STUDENT_GROUP,
        }
        payload.update(overrides)
        return Ticket.objects.create(**payload)

    def test_a_new_ticket_starts_open_normal_and_portal(self):
        ticket = self._ticket()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.priority, TicketPriority.NORMAL)
        self.assertEqual(ticket.channel, TicketChannel.PORTAL)

    def test_a_new_ticket_has_no_owner_no_response_and_is_not_resolved(self):
        ticket = self._ticket()
        self.assertIsNone(ticket.assignee_id)
        self.assertIsNone(ticket.first_response_at)
        self.assertIsNone(ticket.resolved_at)
        self.assertIsNone(ticket.deleted_at)

    def test_region_defaults_to_the_empty_unknown_bucket(self):
        self.assertEqual(self._ticket().region, "")

    def test_ticket_number_is_unique(self):
        self._ticket()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._ticket(subject="A duplicate number")

    def test_deleted_at_is_deliberately_unindexed(self):
        # DEC-019 A1: all six existing soft-delete columns on the platform go
        # without an index, and a second migration to add one is exactly what
        # that decision was made to avoid.
        self.assertFalse(Ticket._meta.get_field("deleted_at").db_index)

    def test_body_has_no_model_level_length_cap(self):
        # DEC-019 A2: the 2000-character cap belongs to the submit serializer.
        self.assertIsNone(Ticket._meta.get_field("body").max_length)

    def test_the_anonymous_only_columns_were_not_built(self):
        # DEC-019 A3/A4: both wait on the outstanding client answer.
        field_names = {f.name for f in Ticket._meta.get_fields()}
        self.assertNotIn("contact_email", field_names)
        self.assertNotIn("is_anonymous", field_names)

    def test_the_email_channel_is_reserved_but_never_the_default(self):
        self.assertIn(TicketChannel.EMAIL, TicketChannel.values)
        self.assertEqual(self._ticket().channel, TicketChannel.PORTAL)


class TicketTimelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="student@example.com", password="pass1234")
        self.ticket = Ticket.objects.create(
            ticket_number="SUP-2026-00002",
            subject="Certificate name correction",
            body="My certificate spells my name wrong.",
            category=TicketCategory.CERTIFICATES_RECORDS,
            created_by=self.user,
        )

    def test_messages_hang_off_the_ticket_and_cascade_with_it(self):
        TicketMessage.objects.create(
            ticket=self.ticket,
            author=self.user,
            message_type=TicketMessageType.USER_MESSAGE,
            body="Any update?",
        )
        self.assertEqual(self.ticket.messages.count(), 1)
        self.ticket.delete()
        self.assertEqual(TicketMessage.objects.count(), 0)

    def test_a_system_message_has_no_author(self):
        message = TicketMessage.objects.create(
            ticket=self.ticket,
            message_type=TicketMessageType.SYSTEM,
            body="Thanks — we have received your enquiry.",
        )
        self.assertIsNone(message.author_id)

    def test_attachments_hang_off_a_message_not_the_ticket(self):
        message = TicketMessage.objects.create(
            ticket=self.ticket,
            author=self.user,
            message_type=TicketMessageType.USER_MESSAGE,
            body="Screenshot attached.",
        )
        attachment = TicketAttachment.objects.create(
            message=message,
            storage_key="tickets/abc123.png",
            original_filename="screenshot.png",
            mime_type="image/png",
            size=2048,
        )
        self.assertEqual(message.attachments.get(), attachment)
        message.delete()
        self.assertEqual(TicketAttachment.objects.count(), 0)

    def test_all_five_tables_use_explicit_short_table_names(self):
        self.assertEqual(Ticket._meta.db_table, "tickets")
        self.assertEqual(TicketMessage._meta.db_table, "ticket_messages")
        self.assertEqual(TicketAttachment._meta.db_table, "ticket_attachments")


class DeletingAStudentDoesNotOrphanWhatTheyWroteTests(TestCase):
    """A ticket body is free text a minor wrote about a problem.

    It carries whatever they thought would help us: an address, a phone
    number, a parent's email. The platform already has a rule for that class
    of content — ``chat.Messages.sender_user`` is PROTECT, so an account that
    has ever written a message cannot simply be deleted, and an admin who
    means it passes ``force=True``, which purges the messages first.

    Tickets were SET_NULL and so opted out of it. Deleting a student returned
    "User deleted successfully" while every word they had written stayed in
    the support queue under no name at all, and ``delete_user``'s own
    docstring says "Delete a user and all related data".
    """

    def setUp(self):
        from apps.groups.models import Countries

        self.country = Countries.objects.create(country_name="Australia")
        self.student = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson", country=self.country,
        )
        self.ticket = lifecycle.create_ticket(
            user=self.student,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject="I am being bullied in my group chat",
            body="My address is 12 Example St and my phone is 0400 000 000.",
        )

    def test_a_plain_delete_is_refused_rather_than_leaving_the_text_behind(self):
        from apps.admin.services.user import delete_user

        result = delete_user(self.student.pk)

        self.assertEqual(
            result["msg"],
            "User cannot be deleted because other records reference them",
        )
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=self.ticket.pk).exists())

    def test_a_forced_delete_takes_the_tickets_with_it(self):
        """force=True is the explicit, confirmed action, and it must be total.

        Refusing without offering a way through would just move the problem:
        an admin who genuinely has to erase somebody needs one.
        """
        from apps.admin.services.user import delete_user

        result = delete_user(self.student.pk, force=True)

        self.assertEqual(result["msg"], "User deleted successfully")
        self.assertFalse(User.objects.filter(pk=self.student.pk).exists())
        self.assertFalse(
            Ticket.objects.filter(pk=self.ticket.pk).exists(),
            "the account went and the text they wrote stayed",
        )
        self.assertFalse(
            TicketMessage.objects.filter(ticket_id=self.ticket.pk).exists(),
            "the ticket went and its messages stayed",
        )

    def test_deleting_an_agent_does_not_take_a_student_enquiry_with_them(self):
        """Only tickets they RAISED. Assignment stays SET_NULL.

        A ticket assigned to somebody belongs to whoever asked for help, so an
        agent leaving must not delete it.
        """
        from apps.admin.services.user import delete_user

        agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=agent)
        lifecycle.assign(ticket=self.ticket, actor=agent, assignee=agent)

        result = delete_user(agent.pk, force=True)

        self.assertEqual(result["msg"], "User deleted successfully")
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assignee_id)
        self.assertEqual(self.ticket.created_by_id, self.student.pk)
