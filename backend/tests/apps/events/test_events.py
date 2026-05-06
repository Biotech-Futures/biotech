from django.test import TestCase

# Create your tests here.
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.events.models import EventRsvp, Events

User = get_user_model()

class EventAPITests(APITestCase):
    """
    Minimal test suite for /events/v1 endpoints.
    Covers:
    - GET returns only upcoming events
    - POST works for admin/staff only
    - POST rejected for regular user
    - Validation rules (end time after start time)
    """

    def setUp(self):
        # Create regular and admin users
        self.user = User.objects.create_user(email="user2@gmail.com", password="pass123")
        self.admin = User.objects.create_user(
            email="test_admin@gmail.com", password="admin123", is_staff=True
        )

        # Base URL (adjust if prefix changed)
        self.url = "/events/v1/"

        # Create one upcoming and one past event
        self.future_event = Events.objects.create(
            event_name="Future Event",
            description="Coming soon!",
            start_datetime=timezone.now() + timezone.timedelta(days=3),
            ends_datetime=timezone.now() + timezone.timedelta(days=3, hours=2),
            location="Sydney",
        )
        self.past_event = Events.objects.create(
            event_name="Past Event",
            description="Already happened.",
            start_datetime=timezone.now() - timezone.timedelta(days=5),
            ends_datetime=timezone.now() - timezone.timedelta(days=4, hours=22),
            location="Melbourne",
        )

    # --- GET TESTS ---

    def test_get_events_returns_only_upcoming(self):
        """GET /events/v1/ should return only upcoming events"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle paginated response
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        event_names = [e["event_name"] for e in results]
        self.assertIn("Future Event", event_names)
        self.assertNotIn("Past Event", event_names)

    # --- POST TESTS ---

    def test_admin_can_create_event(self):
        """Admin/staff user can POST successfully"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Events.objects.filter(event_name="Admin Created Event").exists())

    def test_non_admin_cannot_create_event(self):
        """Regular user cannot POST"""
        self.client.force_authenticate(user=self.user)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Events.objects.filter(event_name="Admin Created Event", host_user=self.user).exists())

    def test_validation_error_if_end_before_start(self):
        """POST with invalid datetime order should fail"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ends_datetime", str(response.data))

    def test_cannot_create_event_in_past(self):
        """POST with start_datetime in the past should fail"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Past Event",
            "description": "This event is in the past",
            "start_datetime": (timezone.now() - timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() - timezone.timedelta(hours=22)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_datetime", str(response.data))
        self.assertIn("Cannot create events in the past", str(response.data))


class EventListFiltersAndSearchTests(APITestCase):
    """Tests for FE-page additions to ``GET /events/v1/``:

      - ``?registered=true`` / ``?mine=true`` filter
      - ``?category=`` filter (maps to ``event_type``)
      - ``?search=`` over event_name / description
      - ``?page_size=`` honored by the list pagination
      - ``"registered": bool`` field on every row
    """

    url = "/events/v1/"

    def setUp(self):
        self.user = User.objects.create_user(email="reg-user@test.com", password="pw")
        self.other = User.objects.create_user(email="other@test.com", password="pw")

        now = timezone.now()
        self.workshop = Events.objects.create(
            event_name="BioTech Futures Workshop",
            description="Introductory workshop for students and mentors.",
            start_datetime=now + timezone.timedelta(days=2),
            ends_datetime=now + timezone.timedelta(days=2, hours=2),
            location="Online",
            event_type=Events.EventTypeChoices.WORKSHOP,
        )
        self.webinar = Events.objects.create(
            event_name="Career Pathways Webinar",
            description="Q&A session about industry placements.",
            start_datetime=now + timezone.timedelta(days=4),
            ends_datetime=now + timezone.timedelta(days=4, hours=1),
            location="Zoom",
            event_type=Events.EventTypeChoices.WEBINAR,
        )
        self.networking = Events.objects.create(
            event_name="Sydney Networking Mixer",
            description="Casual networking with mentors.",
            start_datetime=now + timezone.timedelta(days=6),
            ends_datetime=now + timezone.timedelta(days=6, hours=3),
            location="Sydney",
            event_type=Events.EventTypeChoices.NETWORKING,
        )

        # ``self.user`` is registered for the workshop only.
        EventRsvp.objects.create(
            event=self.workshop,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.GOING,
            responded_at=timezone.now(),
        )

    # ----- registered / mine filter -----------------------------------

    def test_registered_true_returns_only_user_rsvps(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?registered=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    def test_mine_true_is_alias_for_registered_true(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?mine=true")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    def test_registered_false_returns_complement(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?registered=false")
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {self.webinar.id, self.networking.id})

    def test_anonymous_registered_true_returns_empty(self):
        response = self.client.get(self.url + "?registered=true")
        self.assertEqual(response.data["results"], [])

    def test_declined_rsvp_not_treated_as_registered(self):
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?registered=true")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    # ----- registered field on every row ------------------------------

    def test_registered_field_true_for_user_rsvps(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        rows = {row["id"]: row for row in response.data["results"]}
        self.assertTrue(rows[self.workshop.id]["registered"])
        self.assertFalse(rows[self.webinar.id]["registered"])
        self.assertFalse(rows[self.networking.id]["registered"])

    def test_registered_field_false_for_anonymous(self):
        response = self.client.get(self.url)
        for row in response.data["results"]:
            self.assertFalse(row["registered"])

    # ----- category filter --------------------------------------------

    def test_category_filter_matches_event_type_case_insensitive(self):
        response = self.client.get(self.url + "?category=Workshop")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    def test_category_filter_unknown_returns_empty(self):
        response = self.client.get(self.url + "?category=mentor")
        self.assertEqual(response.data["results"], [])

    # ----- search ------------------------------------------------------

    def test_search_matches_event_name(self):
        response = self.client.get(self.url + "?search=workshop")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    def test_search_matches_description(self):
        response = self.client.get(self.url + "?search=placements")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.webinar.id])

    def test_search_is_case_insensitive(self):
        # DRF's ``SearchFilter`` defaults to ``icontains``; this test
        # locks that contract so a future switch to ``contains`` (or a
        # custom backend) would fail loudly. The fixture event names
        # use Title Case, so an upper-case query proves insensitivity.
        upper = self.client.get(self.url + "?search=WORKSHOP")
        lower = self.client.get(self.url + "?search=workshop")
        upper_ids = [row["id"] for row in upper.data["results"]]
        lower_ids = [row["id"] for row in lower.data["results"]]
        self.assertEqual(upper_ids, [self.workshop.id])
        self.assertEqual(upper_ids, lower_ids)

    def test_search_combines_with_registered_filter(self):
        # ``self.user`` is registered for the workshop only, so a
        # search for "workshop" + ``registered=true`` should still
        # return the workshop, but a search for "networking" +
        # ``registered=true`` should return nothing.
        self.client.force_authenticate(user=self.user)
        positive = self.client.get(self.url + "?search=workshop&registered=true")
        self.assertEqual([row["id"] for row in positive.data["results"]], [self.workshop.id])

        negative = self.client.get(self.url + "?search=networking&registered=true")
        self.assertEqual(negative.data["results"], [])

    # ----- pagination via ?page_size ----------------------------------

    def test_page_size_query_param_is_honored(self):
        response = self.client.get(self.url + "?page_size=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["count"], 3)

    def test_page_size_above_max_is_capped(self):
        # ``EventPagination.max_page_size = 100``; asking for more
        # should not error and must still return at most 100 rows.
        response = self.client.get(self.url + "?page_size=999")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data["results"]), 100)

    def test_pending_rsvp_not_treated_as_registered(self):
        # Locks the GOING-only contract: a PENDING RSVP must NOT
        # surface as ``registered=true`` (per filter or per-row field).
        # If we ever loosen this back to "non-declined", this test
        # is the canary that fails first.
        # ``responded_at`` is left NULL because the model's check
        # constraint forbids a timestamp on a PENDING row.
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )
        self.client.force_authenticate(user=self.user)

        filtered = self.client.get(self.url + "?registered=true")
        self.assertEqual(
            [row["id"] for row in filtered.data["results"]],
            [self.workshop.id],
        )

        listing = self.client.get(self.url)
        rows = {row["id"]: row for row in listing.data["results"]}
        self.assertFalse(rows[self.webinar.id]["registered"])

    def test_maybe_rsvp_not_treated_as_registered(self):
        # Same contract guard, but for MAYBE — keeps the GOING-only
        # rule symmetric across the three non-going statuses.
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.MAYBE,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?registered=true")
        self.assertEqual(
            [row["id"] for row in response.data["results"]],
            [self.workshop.id],
        )


class EventRegisterActionTests(APITestCase):
    """Tests for ``POST /events/v1/{id}/register/``."""

    def setUp(self):
        self.user = User.objects.create_user(email="reg@test.com", password="pw")
        now = timezone.now()
        self.future_event = Events.objects.create(
            event_name="Upcoming Workshop",
            description="Open for registration.",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=2),
            location="Online",
        )
        self.past_event = Events.objects.create(
            event_name="Closed Workshop",
            description="Already over.",
            start_datetime=now - timezone.timedelta(days=2),
            ends_datetime=now - timezone.timedelta(days=2) + timezone.timedelta(hours=1),
            location="Online",
        )

    def _url(self, event_id):
        return f"/events/v1/{event_id}/register/"

    def test_authenticated_user_can_register_returns_200(self):
        # Spec: register always returns 200, regardless of whether
        # this is the first call or an idempotent repeat. Locks the
        # contract documented in the API guide ("first call → 200").
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.future_event.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_id"], self.future_event.id)
        self.assertEqual(response.data["user_id"], self.user.id)
        self.assertTrue(response.data["registered"])
        self.assertIsNotNone(response.data["registered_at"])

        # The RSVP row exists AND is in the GOING state — the response
        # would lie if we created a row in any other status.
        rsvp = EventRsvp.objects.get(event=self.future_event, user=self.user)
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.GOING)

    def test_repeat_registration_is_idempotent_returns_200(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.post(self._url(self.future_event.id))
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(self._url(self.future_event.id))
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data["registered"])

        # Only one RSVP row for this user/event combination.
        self.assertEqual(
            EventRsvp.objects.filter(event=self.future_event, user=self.user).count(),
            1,
        )

    def test_register_for_missing_event_returns_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(999999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_register_for_past_event_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.past_event.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_for_soft_deleted_event_returns_404(self):
        self.future_event.deleted_at = timezone.now()
        self.future_event.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.future_event.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_register_is_rejected(self):
        response = self.client.post(self._url(self.future_event.id))
        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )

    def test_register_after_decline_flips_status_to_going(self):
        # Regression guard for the ``update_or_create`` choice in
        # ``register_user_for_event``. With the older ``get_or_create``
        # path, a previously-DECLINED RSVP would be returned untouched
        # and the FE would receive ``registered=true`` on a row whose
        # underlying RSVP was still DECLINED — a quiet lie. The flip
        # is what makes the response truthful.
        EventRsvp.objects.create(
            event=self.future_event,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.future_event.id))

        # Spec: register always returns 200; this exercises the
        # "row existed but in a different status" branch.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["registered"])

        rsvp = EventRsvp.objects.get(event=self.future_event, user=self.user)
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.GOING)

        # And exactly one row — the existing one was updated, not
        # duplicated.
        self.assertEqual(
            EventRsvp.objects.filter(event=self.future_event, user=self.user).count(),
            1,
        )
