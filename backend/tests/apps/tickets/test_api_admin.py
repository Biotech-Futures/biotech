import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import Countries
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import lifecycle
from apps.tickets.services.attachments import stored_attachments
from apps.users.models import AdminScope

User = get_user_model()

QUEUE = "/api/v1/admin/tickets/"
_MEDIA = tempfile.mkdtemp(prefix="ticket-admin-tests-")


def pdf(name="note.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4" + b"0" * 128, content_type="application/pdf")


@override_settings(MEDIA_ROOT=_MEDIA)
class AdminTicketAPITestCase(APITestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.australia = Countries.objects.create(country_name="Australia")
        self.brazil = Countries.objects.create(country_name="Brazil")

        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson", country=self.australia,
        )
        self.other_requester = User.objects.create_user(
            email="bruno@example.com", password="pass1234",
            first_name="Bruno", last_name="Silva", country=self.brazil,
        )
        # A support agent who is not an admin — the case the whole role exists
        # for.
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass1234",
            first_name="Ada", last_name="Lin",
        )
        AdminScope.objects.create(user=self.admin)
        self.outsider = User.objects.create_user(
            email="nobody@example.com", password="pass1234",
            first_name="Nia", last_name="Bell",
        )
        self.client.force_login(self.agent)

    def tearDown(self):
        reset_managed_storage_caches()

    def make_ticket(self, owner=None, subject="Cannot access group workspace", **fields):
        ticket = lifecycle.create_ticket(
            user=owner or self.requester,
            category=fields.pop("category", TicketCategory.PROGRAMS_GROUPS),
            subject=subject,
            body="I get an error opening my group.",
        )
        if fields:
            Ticket.objects.filter(pk=ticket.pk).update(**fields)
            ticket.refresh_from_db()
        return ticket


class QueueAccessTests(AdminTicketAPITestCase):
    def test_a_support_agent_who_is_not_an_admin_can_work_the_queue(self):
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_200_OK)

    def test_an_admin_can_work_the_queue_without_a_support_row(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_200_OK)

    def test_an_ordinary_user_is_refused(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_403_FORBIDDEN)

    def test_the_support_agent_is_still_shut_out_of_the_rest_of_the_admin_area(self):
        # Nothing was changed to achieve this: every other admin endpoint is
        # already gated on AdminScope, which the agent does not have.
        response = self.client.get("/api/v1/admin/user/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_granting_support_access_is_admins_only(self):
        response = self.client.post(f"{QUEUE}support-scope/", {"userId": self.outsider.pk})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class QueueRowTests(AdminTicketAPITestCase):
    def test_the_row_reports_the_support_clock_not_the_requesters(self):
        ticket = self.make_ticket()
        lifecycle.add_internal_note(ticket=ticket, actor=self.agent, body="Internal.")
        ticket.refresh_from_db()

        row = self.client.get(QUEUE).json()["data"]["items"][0]
        self.assertEqual(row["supportUpdatedAt"][:19], ticket.support_updated_at.isoformat()[:19])
        self.assertNotIn("lastUpdated", row)

    def test_a_screening_raised_ticket_is_not_labelled_anonymous(self):
        # created_by is null on those, and a naive "no requester means
        # anonymous" would mislabel every one of them.
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(created_by=None, channel="ai_screening")

        row = self.client.get(QUEUE).json()["data"]["items"][0]
        self.assertFalse(row["user"]["anonymous"])

    def test_the_queue_is_sorted_by_most_recent_support_activity(self):
        older = self.make_ticket(subject="Older")
        self.make_ticket(subject="Newer")
        lifecycle.add_internal_note(ticket=older, actor=self.agent, body="Bumping.")

        items = self.client.get(QUEUE).json()["data"]["items"]
        self.assertEqual(items[0]["id"], older.pk)

    def test_a_soft_deleted_ticket_leaves_the_queue(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())

        data = self.client.get(QUEUE).json()["data"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])


class QueueFilterTests(AdminTicketAPITestCase):
    def setUp(self):
        super().setUp()
        self.au = self.make_ticket(subject="Australian one")
        self.br = self.make_ticket(owner=self.other_requester, subject="Brazilian one")
        self.unknown = self.make_ticket(subject="No region on file", region="")
        Ticket.objects.filter(pk=self.au.pk).update(region="Australia")
        Ticket.objects.filter(pk=self.br.pk).update(region="Brazil")

    def ids_for(self, **params):
        return {row["id"] for row in self.client.get(QUEUE, params).json()["data"]["items"]}

    def test_filtering_by_region(self):
        self.assertEqual(self.ids_for(region="Brazil"), {self.br.pk})

    def test_the_unknown_region_bucket_is_selectable(self):
        # Without a sentinel this bucket has a name in the dropdown but an
        # empty value, and an empty query parameter reads as "no filter".
        self.assertEqual(self.ids_for(region="__unknown__"), {self.unknown.pk})

    def test_filtering_by_status(self):
        lifecycle.claim(ticket=self.au, actor=self.agent)
        self.assertEqual(self.ids_for(status="in_progress"), {self.au.pk})

    def test_filtering_by_category(self):
        Ticket.objects.filter(pk=self.br.pk).update(category=TicketCategory.ACCOUNT_ACCESS)
        self.assertEqual(self.ids_for(category="account_access"), {self.br.pk})

    def test_filtering_by_priority(self):
        Ticket.objects.filter(pk=self.au.pk).update(priority=TicketPriority.HIGH)
        self.assertEqual(self.ids_for(priority="high"), {self.au.pk})

    def test_filtering_by_assignee(self):
        lifecycle.claim(ticket=self.br, actor=self.agent)
        self.assertEqual(self.ids_for(assignee=self.agent.pk), {self.br.pk})

    def test_filters_combine(self):
        Ticket.objects.filter(pk=self.au.pk).update(priority=TicketPriority.HIGH)
        self.assertEqual(self.ids_for(region="Australia", priority="high"), {self.au.pk})
        self.assertEqual(self.ids_for(region="Brazil", priority="high"), set())

    def test_search_finds_a_ticket_by_its_number(self):
        self.assertEqual(self.ids_for(search=self.br.ticket_number), {self.br.pk})

    def test_search_finds_a_ticket_by_its_subject(self):
        self.assertEqual(self.ids_for(search="Brazilian"), {self.br.pk})

    def test_search_finds_a_ticket_by_the_requesters_name(self):
        self.assertEqual(self.ids_for(search="Bruno"), {self.br.pk})

    def test_search_finds_a_ticket_by_the_requesters_email(self):
        self.assertEqual(self.ids_for(search="bruno@example.com"), {self.br.pk})

    def test_search_does_not_reach_soft_deleted_tickets(self):
        Ticket.objects.filter(pk=self.br.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.ids_for(search="Brazilian"), set())


@override_settings(
    MEDIA_ROOT=_MEDIA,
    TICKET_SLA_HIGH_HOURS=4,
    TICKET_SLA_NORMAL_HOURS=24,
    TICKET_SLA_LOW_HOURS=72,
)
class OverdueTests(AdminTicketAPITestCase):
    def aged(self, *, hours, priority=TicketPriority.HIGH, **fields):
        ticket = self.make_ticket(priority=priority, **fields)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=hours)
        )
        ticket.refresh_from_db()
        return ticket

    def overdue_count(self):
        return self.client.get(f"{QUEUE}summary/").json()["data"]["overdue"]

    def test_a_high_priority_ticket_is_not_overdue_just_before_its_deadline(self):
        self.aged(hours=3, priority=TicketPriority.HIGH)
        self.assertEqual(self.overdue_count(), 0)

    def test_a_high_priority_ticket_is_overdue_just_after_its_deadline(self):
        self.aged(hours=5, priority=TicketPriority.HIGH)
        self.assertEqual(self.overdue_count(), 1)

    def test_each_priority_has_its_own_deadline(self):
        self.aged(hours=5, priority=TicketPriority.NORMAL)   # 24h allowed
        self.aged(hours=30, priority=TicketPriority.LOW)     # 72h allowed
        self.assertEqual(self.overdue_count(), 0)

    def test_a_ticket_that_has_been_answered_is_never_overdue(self):
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="On it.")
        self.assertEqual(self.overdue_count(), 0)

    def test_a_resolved_ticket_is_never_overdue(self):
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.RESOLVED, actor=self.agent
        )
        self.assertEqual(self.overdue_count(), 0)

    def test_the_queue_row_carries_the_same_verdict_as_the_counter(self):
        self.aged(hours=5, priority=TicketPriority.HIGH)
        row = self.client.get(QUEUE).json()["data"]["items"][0]
        self.assertTrue(row["overdue"])


class SummaryTests(AdminTicketAPITestCase):
    def test_the_four_counters_match_a_hand_count(self):
        self.make_ticket(subject="Untouched and open")
        claimed = self.make_ticket(subject="Being worked on")
        lifecycle.claim(ticket=claimed, actor=self.agent)
        waiting = self.make_ticket(subject="Waiting on the requester")
        lifecycle.claim(ticket=waiting, actor=self.agent)
        lifecycle.mark_pending(ticket=waiting, actor=self.agent)
        done = self.make_ticket(subject="Finished")
        lifecycle.resolve(ticket=done, actor=self.agent)

        data = self.client.get(f"{QUEUE}summary/").json()["data"]
        self.assertEqual(data["open"], 1)
        self.assertEqual(data["pendingUser"], 1)
        # Unassigned counts only tickets still needing work: the resolved one
        # has no owner either, but nobody has to pick it up.
        self.assertEqual(data["unassigned"], 1)
        self.assertEqual(data["overdue"], 0)


class PatchTests(AdminTicketAPITestCase):
    def test_status_and_assignee_together_are_rejected(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"status": "in_progress", "assignee": self.agent.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_priority_may_accompany_a_status_change(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"status": "pending_user", "priority": "high"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertEqual(ticket.priority, TicketPriority.HIGH)

    def test_changing_the_priority_is_invisible_to_the_requester(self):
        ticket = self.make_ticket()
        before_user, before_support = ticket.updated_at, ticket.support_updated_at
        messages_before = ticket.messages.count()

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"priority": "high"}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_handing_a_started_ticket_over_is_invisible_to_the_requester(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        before_user = ticket.updated_at
        messages_before = ticket.messages.count()

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": self.admin.pk}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.admin.pk)
        self.assertEqual(ticket.updated_at, before_user)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_an_empty_patch_is_rejected(self):
        ticket = self.make_ticket()
        response = self.client.patch(f"{QUEUE}{ticket.pk}/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_ticket_cannot_be_assigned_to_someone_who_cannot_open_it(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": self.outsider.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BulkAssignTests(AdminTicketAPITestCase):
    def test_only_the_tickets_waiting_in_the_pool_get_a_timeline_message(self):
        open_ticket = self.make_ticket(subject="In the pool")
        waiting = self.make_ticket(subject="Waiting on the requester")
        lifecycle.claim(ticket=waiting, actor=self.agent)
        lifecycle.mark_pending(ticket=waiting, actor=self.agent)
        waiting_messages_before = waiting.messages.count()
        open_messages_before = open_ticket.messages.count()

        response = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [open_ticket.pk, waiting.pk], "assigneeId": self.admin.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        open_ticket.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(open_ticket.messages.count(), open_messages_before + 1)
        self.assertEqual(waiting.messages.count(), waiting_messages_before)
        self.assertEqual(waiting.status, TicketStatus.PENDING_USER)

    def test_an_unknown_id_is_reported_without_sinking_the_batch(self):
        ticket = self.make_ticket()
        results = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk, 999999], "assigneeId": self.admin.pk},
            format="json",
        ).json()["data"]["results"]
        self.assertEqual(
            results,
            [{"ticketId": ticket.pk, "ok": True},
             {"ticketId": 999999, "ok": False, "error": "not found"}],
        )

    def test_a_soft_deleted_ticket_cannot_be_swept_up(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())
        results = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk], "assigneeId": self.admin.pk},
            format="json",
        ).json()["data"]["results"]
        self.assertEqual(results, [{"ticketId": ticket.pk, "ok": False, "error": "not found"}])


class SupportMessageTests(AdminTicketAPITestCase):
    def test_an_agent_can_reply(self):
        ticket = self.make_ticket()
        response = self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "support_reply", "body": "Looking into it now."},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.first_response_at)

    def test_the_support_view_of_the_timeline_includes_internal_notes(self):
        ticket = self.make_ticket()
        self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "internal_note", "body": "Escalating internally."},
        )
        payload = self.client.get(f"{QUEUE}{ticket.pk}/").json()["data"]
        self.assertIn("internal_note", [m["messageType"] for m in payload["messages"]])

    def test_an_internal_note_does_not_count_as_a_first_response(self):
        ticket = self.make_ticket()
        self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "internal_note", "body": "Internal only."},
        )
        ticket.refresh_from_db()
        self.assertIsNone(ticket.first_response_at)

    def test_the_support_side_can_download_a_file_from_an_internal_note(self):
        ticket = self.make_ticket()
        with stored_attachments([pdf("internal.pdf")]) as rows:
            note = lifecycle.add_internal_note(
                ticket=ticket, actor=self.agent, body="Internal.", attachments=rows
            )
        attachment_id = note.attachments.get().pk

        response = self.client.get(f"{QUEUE}{ticket.pk}/attachments/{attachment_id}/")
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND))


class HistoryTests(AdminTicketAPITestCase):
    def test_the_history_reads_oldest_first(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.admin)
        lifecycle.resolve(ticket=ticket, actor=self.admin)

        rows = self.client.get(f"{QUEUE}{ticket.pk}/history/").json()["data"]
        self.assertEqual([r["action"] for r in rows], ["assign", "assign", "resolve"])
        timestamps = [r["createdAt"] for r in rows]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_the_history_says_who_moved_it_and_between_whom(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.admin)

        handover = self.client.get(f"{QUEUE}{ticket.pk}/history/").json()["data"][-1]
        self.assertEqual(handover["actor"]["id"], self.agent.pk)
        self.assertEqual(handover["beforeState"], {"assignee_id": self.agent.pk})
        self.assertEqual(handover["afterState"], {"assignee_id": self.admin.pk})

    def test_an_agent_who_is_not_an_admin_can_read_it(self):
        # The platform's own audit endpoint is gated on is_staff, which would
        # shut this agent out of the record of their own queue.
        ticket = self.make_ticket()
        self.assertEqual(
            self.client.get(f"{QUEUE}{ticket.pk}/history/").status_code,
            status.HTTP_200_OK,
        )


class RosterTests(AdminTicketAPITestCase):
    def test_the_assignee_list_holds_agents_and_admins_once_each(self):
        SupportScope.objects.create(user=self.admin)  # both rows for one person
        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        ids = [row["id"] for row in rows]
        self.assertEqual(sorted(ids), sorted({self.agent.pk, self.admin.pk}))
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_region_dropdown_ends_with_the_unknown_bucket(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(region="Australia")
        rows = self.client.get(f"{QUEUE}regions/").json()["data"]
        self.assertEqual(rows[-1], {"value": "__unknown__", "label": "Unknown"})
        self.assertIn({"value": "Australia", "label": "Australia"}, rows)

    def test_an_admin_can_grant_and_revoke_support_access(self):
        self.client.force_login(self.admin)
        granted = self.client.post(f"{QUEUE}support-scope/", {"userId": self.outsider.pk})
        self.assertEqual(granted.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SupportScope.objects.filter(user=self.outsider).exists())

        revoked = self.client.delete(f"{QUEUE}support-scope/{self.outsider.pk}/")
        self.assertEqual(revoked.status_code, status.HTTP_200_OK)
        self.assertFalse(SupportScope.objects.filter(user=self.outsider).exists())


class MeEndpointTests(AdminTicketAPITestCase):
    def flags_for(self, user):
        self.client.force_login(user)
        payload = self.client.get("/api/v1/users/me/").json()
        return payload["isAdmin"], payload["isSupport"]

    def test_an_agent_is_support_but_not_admin(self):
        self.assertEqual(self.flags_for(self.agent), (False, True))

    def test_an_admin_is_both(self):
        # One flag could not tell these two rows apart, which is why the
        # endpoint returns two.
        self.assertEqual(self.flags_for(self.admin), (True, True))

    def test_an_ordinary_user_is_neither(self):
        self.assertEqual(self.flags_for(self.outsider), (False, False))

    def test_the_user_list_response_did_not_grow_the_two_flags(self):
        self.client.force_login(self.admin)
        rows = self.client.get("/api/v1/admin/user/").json()["data"]["items"]
        self.assertTrue(rows)
        self.assertNotIn("isSupport", rows[0])
