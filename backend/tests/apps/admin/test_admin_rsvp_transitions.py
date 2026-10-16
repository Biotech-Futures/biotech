from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.events.models import EventRsvp, Events
from apps.users.models import AdminScope


class AdminRsvpTransitionTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(email="rsvp-admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        users = [User.objects.create_user(email=f"rsvp-{i}@example.com", password="pw") for i in range(4)]
        self.attendee, self.oldest, self.newest, self.extra = users
        now = timezone.now()
        self.event = Events.objects.create(
            event_name="Capacity one", max_attendees=1,
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
        )
        self.accepted = EventRsvp.objects.create(
            event=self.event, user=self.attendee, rsvp_status="accepted", responded_at=now,
        )
        for index, user in enumerate((self.oldest, self.newest)):
            EventRsvp.objects.create(
                event=self.event, user=user, rsvp_status="waitlisted",
                responded_at=now - timezone.timedelta(minutes=2 - index),
            )
        self.client.force_authenticate(self.admin)

    def _change(self, route, new_status):
        if route == "admin":
            return self.client.put(f"/api/v1/admin/event/rsvp/{self.accepted.pk}/", {
                "rsvpStatus": new_status,
            }, format="json")
        if route == "invite":
            return self.client.post(f"/api/v1/events/{self.event.pk}/rsvp/{self.attendee.pk}/", {
                "rsvp_status": new_status,
            }, format="json")
        return self.client.post(f"/api/v1/events/{self.event.pk}/rsvp/bulk/", {
            "user_ids": [self.attendee.pk], "rsvp_status": new_status,
        }, format="json")

    def test_all_admin_routes_promote_oldest_waitlisted_when_slot_is_released(self):
        for route in ("admin", "invite", "bulk"):
            with self.subTest(route=route):
                for index, user in enumerate((self.oldest, self.newest)):
                    EventRsvp.objects.filter(event=self.event, user=user).update(
                        rsvp_status="waitlisted",
                        responded_at=timezone.now() - timezone.timedelta(minutes=2 - index),
                    )
                EventRsvp.objects.filter(pk=self.accepted.pk).update(rsvp_status="accepted")
                response = self._change(route, "declined")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(EventRsvp.objects.get(event=self.event, user=self.oldest).rsvp_status, "accepted")
                self.assertEqual(EventRsvp.objects.get(event=self.event, user=self.newest).rsvp_status, "waitlisted")
                self.assertEqual(EventRsvp.objects.filter(event=self.event, rsvp_status="accepted").count(), 1)

    def test_pending_create_has_no_response_timestamp(self):
        self.client.raise_request_exception = False
        response = self.client.post(f"/api/v1/admin/event/{self.event.pk}/rsvp/", {
            "userId": self.extra.pk, "rsvpStatus": "pending",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["data"]["respondedAt"])
        self.assertIsNone(EventRsvp.objects.get(event=self.event, user=self.extra).responded_at)

    def test_reset_to_pending_clears_timestamp_and_releases_slot(self):
        self.client.raise_request_exception = False
        response = self._change("admin", "pending")
        self.assertEqual(response.status_code, 200)
        self.accepted.refresh_from_db()
        self.assertIsNone(self.accepted.responded_at)
        self.assertEqual(self.accepted.rsvp_status, "pending")
        self.assertEqual(EventRsvp.objects.get(event=self.event, user=self.oldest).rsvp_status, "accepted")

    def test_admin_create_respects_capacity(self):
        response = self.client.post(f"/api/v1/admin/event/{self.event.pk}/rsvp/", {
            "user_id": self.extra.pk, "rsvp_status": "accepted",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["rsvpStatus"], "waitlisted")

    def test_all_admin_routes_keep_existing_accepted_slot(self):
        for route in ("admin", "invite", "bulk"):
            with self.subTest(route=route):
                response = self._change(route, "accepted")
                self.assertEqual(response.status_code, 200)
                self.accepted.refresh_from_db()
                self.assertEqual(self.accepted.rsvp_status, "accepted")
                self.assertEqual(EventRsvp.objects.filter(event=self.event, rsvp_status="accepted").count(), 1)

    def test_promotion_notification_runs_after_commit(self):
        with patch("apps.events.promotion_email.notify_waitlist_promoted") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._change("admin", "declined")
                self.assertEqual(response.status_code, 200)
                notify.assert_not_called()
            notify.assert_called_once_with(event_id=self.event.pk, user_id=self.oldest.pk)

    def test_bulk_withdrawal_notifies_only_final_promoted_participant(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/api/v1/events/{self.event.pk}/rsvp/bulk/", {
                "user_ids": [self.attendee.pk, self.oldest.pk], "rsvp_status": "declined",
            }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EventRsvp.objects.get(event=self.event, user=self.oldest).rsvp_status, "declined")
        self.assertEqual([message.to for message in mail.outbox], [[self.newest.email]])

    def test_explicit_waitlist_does_not_promote_the_departing_participant(self):
        EventRsvp.objects.filter(event=self.event, rsvp_status="waitlisted").delete()
        response = self._change("admin", "waitlisted")
        self.assertEqual(response.status_code, 200)
        self.accepted.refresh_from_db()
        self.assertEqual(self.accepted.rsvp_status, "waitlisted")

    def test_invalid_admin_status_returns_400_without_modification(self):
        response = self._change("admin", "invalid")
        self.assertEqual(response.status_code, 400)
        self.accepted.refresh_from_db()
        self.assertEqual(self.accepted.rsvp_status, "accepted")

    def test_admin_routes_remain_forbidden_for_non_admin(self):
        self.client.force_authenticate(self.extra)
        for route in ("admin", "invite", "bulk"):
            with self.subTest(route=route):
                self.assertEqual(self._change(route, "declined").status_code, 403)

    def test_admin_response_keeps_user_metadata(self):
        self.extra.first_name = "Ada"
        self.extra.last_name = "Lovelace"
        self.extra.save(update_fields=["first_name", "last_name"])
        response = self.client.post(f"/api/v1/admin/event/{self.event.pk}/rsvp/", {
            "userId": self.extra.pk, "rsvpStatus": "pending",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        rsvp_id = response.data["data"]["id"]
        updated = self.client.put(f"/api/v1/admin/event/rsvp/{rsvp_id}/", {
            "rsvpStatus": "tentative",
        }, format="json")
        self.assertEqual(updated.status_code, 200)
        for result in (response, updated):
            self.assertEqual(result.data["data"]["userName"], "Ada Lovelace")
            self.assertEqual(result.data["data"]["userEmail"], self.extra.email)
            self.assertEqual(result.data["data"]["userRole"], "student")
            self.assertEqual(result.data["data"]["firstName"], "Ada")
            self.assertEqual(result.data["data"]["lastName"], "Lovelace")

    def test_invite_rejects_invalid_status_and_defaults_to_pending(self):
        url = f"/api/v1/events/{self.event.pk}/rsvp/{self.extra.pk}/"
        self.client.raise_request_exception = False
        self.assertEqual(self.client.post(url, {"rsvp_status": "invalid"}, format="json").status_code, 400)
        self.assertFalse(EventRsvp.objects.filter(event=self.event, user=self.extra).exists())
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 200)
        rsvp = EventRsvp.objects.get(event=self.event, user=self.extra)
        self.assertEqual(rsvp.rsvp_status, "pending")
        self.assertIsNone(rsvp.responded_at)
