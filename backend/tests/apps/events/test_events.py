from django.test import TestCase

# Create your tests here.
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.events.models import (
    EventRsvp,
    EventTargetGroup,
    Events,
)
from apps.groups.models import (
    Countries,
    CountryStates,
    GroupMembership,
    Groups,
    Tracks,
)
from apps.users.models import AdminScope

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


# ---------------------------------------------------------------------------
# Role-model visibility gate.
#
# Per the Roles & Permissions structure, events are pushed by admins
# and users RSVP to events they're targeted by — they don't self-add
# to arbitrary events. These tests exercise the gate against the
# existing ``/register/`` endpoint (which now routes through the same
# ``set_user_rsvp`` helper as ``/rsvp/``).
# ---------------------------------------------------------------------------


class EventRegisterVisibilityGateTests(APITestCase):
    """Permission-gate behavior for ``POST /events/v1/{id}/register/``.

    The fixture builds two tracks, two groups (one per track), and a
    user who is a member of *only* the first group. We then create
    several events with different targeting axes and verify the gate
    permits / forbids correctly.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="member@test.com", password="pw")
        self.outsider = User.objects.create_user(email="outsider@test.com", password="pw")

        # Tracks require a state (country → state → track), so build
        # the chain. Mirrors the dashboard test fixtures.
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        self.group_a = Groups.objects.create(group_name="Group A", track=self.track_a)
        self.group_b = Groups.objects.create(group_name="Group B", track=self.track_b)

        # ``self.user`` is a student member of group_a only. Both
        # ``self.user`` and ``self.outsider`` have no GroupMembership
        # in group_b and no track on the User row.
        GroupMembership.objects.create(
            group=self.group_a,
            user=self.user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        now = timezone.now()
        self.untargeted_event = Events.objects.create(
            event_name="Org-wide Town Hall",
            description="Open to everyone.",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        self.event_for_group_a = Events.objects.create(
            event_name="Group A Workshop",
            description="Members of Group A only.",
            start_datetime=now + timezone.timedelta(days=2),
            ends_datetime=now + timezone.timedelta(days=2, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_a, group=self.group_a)

        self.event_for_group_b = Events.objects.create(
            event_name="Group B Workshop",
            description="Members of Group B only.",
            start_datetime=now + timezone.timedelta(days=3),
            ends_datetime=now + timezone.timedelta(days=3, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_b, group=self.group_b)

    def _url(self, event_id):
        return f"/events/v1/{event_id}/register/"

    def test_untargeted_event_is_open_to_any_authenticated_user(self):
        # An event with no targets is platform-wide; any logged-in
        # user can register. This is the path the existing register
        # tests rely on, so a regression here would cascade.
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(self._url(self.untargeted_event.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["registered"])

    def test_member_of_target_group_can_register(self):
        # ``self.user`` IS a member of group_a, the event's only target.
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.event_for_group_a.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            EventRsvp.objects.filter(
                event=self.event_for_group_a, user=self.user
            ).exists()
        )

    def test_non_target_user_is_blocked_with_403(self):
        # ``self.user`` is NOT a member of group_b. The role-model
        # contract says students cannot self-add to events their
        # admin didn't target their group with. Locking this down is
        # the whole point of the gate.
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.event_for_group_b.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # And no RSVP row was created — the failure is total, not partial.
        self.assertFalse(
            EventRsvp.objects.filter(
                event=self.event_for_group_b, user=self.user
            ).exists()
        )

    def test_existing_invite_overrides_targeting(self):
        # If an admin pre-creates an RSVP (any status, including
        # DECLINED), the user is treated as an explicit invitee and
        # may always update their state. Without this, a declined
        # user would lose the ability to change their mind — exactly
        # the bug ``set_user_rsvp`` is designed to avoid.
        EventRsvp.objects.create(
            event=self.event_for_group_b,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.event_for_group_b.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rsvp = EventRsvp.objects.get(
            event=self.event_for_group_b, user=self.user
        )
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.GOING)


# ---------------------------------------------------------------------------
# Full user-side RSVP control: ``POST /events/v1/{id}/rsvp/``.
# ---------------------------------------------------------------------------


class EventRsvpSetActionTests(APITestCase):
    """End-to-end coverage for the new ``/rsvp/`` endpoint.

    Same gate as ``/register/`` (covered above); these tests focus on
    the bits unique to ``/rsvp/`` — accepting going/maybe/declined,
    rejecting pending, idempotency on status changes.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="rsvp-user@test.com", password="pw")
        now = timezone.now()
        self.future_event = Events.objects.create(
            event_name="Open Event",
            description="No targets — open to all.",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        self.past_event = Events.objects.create(
            event_name="Past Event",
            description="Already over.",
            start_datetime=now - timezone.timedelta(days=2),
            ends_datetime=now - timezone.timedelta(days=2) + timezone.timedelta(hours=1),
            location="Online",
        )

    def _url(self, event_id):
        return f"/events/v1/{event_id}/rsvp/"

    def test_user_can_rsvp_going(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.GOING},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.GOING)
        self.assertTrue(response.data["registered"])
        self.assertIsNotNone(response.data["responded_at"])

        rsvp = EventRsvp.objects.get(event=self.future_event, user=self.user)
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.GOING)

    def test_user_can_rsvp_maybe(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.MAYBE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.MAYBE)
        # ``registered`` is the FE-facing alias for "going", so MAYBE
        # must not surface as registered=true.
        self.assertFalse(response.data["registered"])

    def test_user_can_rsvp_declined(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.DECLINED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.DECLINED)
        self.assertFalse(response.data["registered"])

    def test_status_transitions_update_in_place(self):
        # going → maybe → declined → going. Each call updates the
        # row in place; we never end up with multiple RSVPs for the
        # same (event, user) pair.
        self.client.force_authenticate(user=self.user)
        for new_status in [
            EventRsvp.RsvpStatus.GOING,
            EventRsvp.RsvpStatus.MAYBE,
            EventRsvp.RsvpStatus.DECLINED,
            EventRsvp.RsvpStatus.GOING,
        ]:
            response = self.client.post(
                self._url(self.future_event.id),
                {"rsvp_status": new_status},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["rsvp_status"], new_status)

        self.assertEqual(
            EventRsvp.objects.filter(event=self.future_event, user=self.user).count(),
            1,
        )

    def test_rsvp_pending_is_rejected(self):
        # PENDING is the admin-invite default; a user submitting it
        # would silently overwrite an admin's invite. Locked at the
        # serializer layer.
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.PENDING},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvp_unknown_status_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": "not-a-real-status"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvp_missing_status_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self._url(self.future_event.id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvp_for_past_event_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.past_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.GOING},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvp_missing_event_returns_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(999999),
            {"rsvp_status": EventRsvp.RsvpStatus.GOING},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_rsvp_is_rejected(self):
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.GOING},
            format="json",
        )
        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )

    def test_register_endpoint_blocks_non_targets_too(self):
        # Cross-check that ``/register/`` and ``/rsvp/`` route through
        # the same gate. We seed a targeted event the user is NOT a
        # member of, then try ``/register/`` — must be 403.
        country = Countries.objects.create(country_name="Locked Country")
        state = CountryStates.objects.create(country=country, state_name="Locked State")
        track = Tracks.objects.create(track_name="Locked Track", state=state)
        group = Groups.objects.create(group_name="Locked Group", track=track)
        targeted_event = Events.objects.create(
            event_name="Closed Doors",
            description="Members only.",
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            ends_datetime=timezone.now() + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=targeted_event, group=group)

        self.client.force_authenticate(user=self.user)
        register_resp = self.client.post(f"/events/v1/{targeted_event.id}/register/")
        rsvp_resp = self.client.post(
            f"/events/v1/{targeted_event.id}/rsvp/",
            {"rsvp_status": EventRsvp.RsvpStatus.GOING},
            format="json",
        )
        self.assertEqual(register_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(rsvp_resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Gap 1: write-side admin-scope enforcement on ``POST /events/v1/``.
#
# The role spec says Track Administrators have access *only* to their
# assigned tracks. The previous ``IsAdminOrReadOnly`` permission checked
# ``is_staff`` only, so Track Admins (defined by ``AdminScope`` rows but
# not necessarily ``is_staff``) were locked out of event creation
# entirely. The new ``EventManagePermission`` + ``perform_create``
# track-scope check open the door for Track Admins while keeping the
# scope narrow:
#
#   * Track Admin → may create events whose ``track`` FK is in their
#     scope. Cannot create untargeted events (those reach every user
#     and would be a privilege escalation past their assigned tracks).
#   * Global Admin (``is_staff`` / ``is_superuser`` / ``is_global``
#     ``AdminScope`` row) → unrestricted (any track or untargeted).
# ---------------------------------------------------------------------------


class EventCreatePermissionTests(APITestCase):
    """Tests for write-side admin-scope enforcement on POST /events/v1/."""

    url = "/events/v1/"

    def setUp(self):
        # Track Admin scoped to track_a; another Track Admin scoped
        # to track_b; a Global Admin via ``AdminScope.is_global``;
        # and a regular user as the negative case.
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        self.regular = User.objects.create_user(email="reg@test.com", password="pw")

        self.track_admin_a = User.objects.create_user(
            email="track-admin-a@test.com", password="pw"
        )
        AdminScope.objects.create(
            user=self.track_admin_a, track=self.track_a, is_global=False
        )

        self.track_admin_b = User.objects.create_user(
            email="track-admin-b@test.com", password="pw"
        )
        AdminScope.objects.create(
            user=self.track_admin_b, track=self.track_b, is_global=False
        )

        self.global_admin = User.objects.create_user(
            email="global-admin@test.com", password="pw"
        )
        AdminScope.objects.create(
            user=self.global_admin, track=None, is_global=True
        )

    def _payload(self, *, name="Created Event", track_id=None):
        # ``is_virtual=False`` + a physical ``location`` mirrors the
        # passing fixture in ``EventAPITests`` — the serializer
        # rejects ``is_virtual=True`` *with* a location.
        body = {
            "event_name": name,
            "description": "fixture",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
        }
        if track_id is not None:
            body["track"] = track_id
        return body

    # ----- Track Admin happy path -------------------------------------

    def test_track_admin_can_create_event_in_their_track(self):
        # The whole point of Gap 1: Track Admin A creates a Track A
        # event, no ``is_staff`` required.
        self.client.force_authenticate(user=self.track_admin_a)
        response = self.client.post(
            self.url, self._payload(name="A Event", track_id=self.track_a.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = Events.objects.get(event_name="A Event")
        self.assertEqual(event.track_id, self.track_a.id)

    # ----- Track Admin restrictions -----------------------------------

    def test_track_admin_cannot_create_event_in_other_track(self):
        # Track Admin A has no scope on Track B, so a B-targeted event
        # is forbidden. The 403 + no-row guarantees the failure is
        # total (no half-saved Event).
        self.client.force_authenticate(user=self.track_admin_a)
        response = self.client.post(
            self.url, self._payload(name="B Event", track_id=self.track_b.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Events.objects.filter(event_name="B Event").exists())

    def test_track_admin_cannot_create_untargeted_event(self):
        # An untargeted event is org-wide and reaches every user,
        # which would let Track Admin A push to Track B's audience.
        # Reserved for Global Admins only.
        self.client.force_authenticate(user=self.track_admin_a)
        response = self.client.post(
            self.url, self._payload(name="No-Track Event"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Events.objects.filter(event_name="No-Track Event").exists())

    # ----- Global Admin freedom ---------------------------------------

    def test_global_admin_scope_can_create_untargeted_event(self):
        # ``AdminScope(is_global=True)`` ⇒ ``get_admin_track_ids``
        # returns ``None`` ⇒ no track-scope clamp on POST.
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.post(
            self.url, self._payload(name="Org-wide Event"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Events.objects.filter(event_name="Org-wide Event").exists())

    def test_global_admin_scope_can_create_event_in_any_track(self):
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.post(
            self.url, self._payload(name="Cross-Track Event", track_id=self.track_b.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ----- Regular user remains 403 -----------------------------------

    def test_regular_user_still_cannot_create_event(self):
        # Defense in depth: the new permission must not have widened
        # write access to non-admins. The previous test already covers
        # is_staff=False users; this covers a user with neither
        # is_staff nor any AdminScope row.
        self.client.force_authenticate(user=self.regular)
        response = self.client.post(
            self.url, self._payload(name="Should Fail", track_id=self.track_a.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Gap 2: read-side scoping on ``GET /events/v1/``.
#
# Per the "events are pushed by admin" model, a non-admin user must
# only see events they're a target of. The visibility queryset
# expresses the same gate as ``can_user_rsvp_to_event`` so the read
# and write sides agree: a user who can SEE an event can also RSVP
# to it, and vice-versa.
# ---------------------------------------------------------------------------


class EventListVisibilityScopingTests(APITestCase):
    """Tests for ``visible_events_queryset`` wired into the list view.

    Fixture: two tracks, two groups (one per track). One event per
    targeting axis (untargeted, targets group_a, targets group_b,
    targets track_a directly via FK, targets track_b directly via FK).
    Members and admins should each see a different subset of these.
    """

    url = "/events/v1/"

    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        self.group_a = Groups.objects.create(group_name="Group A", track=self.track_a)
        self.group_b = Groups.objects.create(group_name="Group B", track=self.track_b)

        # Member of group_a only.
        self.member_a = User.objects.create_user(
            email="member-a@test.com", password="pw"
        )
        GroupMembership.objects.create(
            group=self.group_a,
            user=self.member_a,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        # Outsider — no group, no track.
        self.outsider = User.objects.create_user(
            email="outsider@test.com", password="pw"
        )

        # Track Admin scoped to track_a.
        self.track_admin_a = User.objects.create_user(
            email="track-admin-a@test.com", password="pw"
        )
        AdminScope.objects.create(
            user=self.track_admin_a, track=self.track_a, is_global=False
        )

        # Global admin via is_staff (covers the legacy path).
        self.global_admin = User.objects.create_user(
            email="global-admin@test.com", password="pw", is_staff=True
        )

        now = timezone.now()
        self.untargeted = Events.objects.create(
            event_name="Org Town Hall",
            description="Open to all.",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        self.event_for_group_a = Events.objects.create(
            event_name="Group A Workshop",
            description="Members only.",
            start_datetime=now + timezone.timedelta(days=2),
            ends_datetime=now + timezone.timedelta(days=2, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(
            event=self.event_for_group_a, group=self.group_a
        )
        self.event_for_group_b = Events.objects.create(
            event_name="Group B Workshop",
            description="Members only.",
            start_datetime=now + timezone.timedelta(days=3),
            ends_datetime=now + timezone.timedelta(days=3, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(
            event=self.event_for_group_b, group=self.group_b
        )
        self.event_for_track_a = Events.objects.create(
            event_name="Track A Webinar",
            description="Track A direct FK.",
            start_datetime=now + timezone.timedelta(days=4),
            ends_datetime=now + timezone.timedelta(days=4, hours=1),
            location="Online",
            track=self.track_a,
        )
        self.event_for_track_b = Events.objects.create(
            event_name="Track B Webinar",
            description="Track B direct FK.",
            start_datetime=now + timezone.timedelta(days=5),
            ends_datetime=now + timezone.timedelta(days=5, hours=1),
            location="Online",
            track=self.track_b,
        )

    def _list(self, user=None):
        if user is not None:
            self.client.force_authenticate(user=user)
        else:
            self.client.force_authenticate(user=None)
        response = self.client.get(self.url + "?page_size=100")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["event_name"] for row in response.data["results"]}

    # ----- Non-admin member -------------------------------------------

    def test_member_sees_untargeted_and_their_group_and_track(self):
        # Member of group_a + Track A (via group's parent track):
        #   ✓ untargeted (open to all)
        #   ✓ event_for_group_a (group target matches)
        #   ✓ event_for_track_a (track target matches via group's track)
        #   ✗ event_for_group_b (group mismatch)
        #   ✗ event_for_track_b (track mismatch)
        names = self._list(user=self.member_a)
        self.assertIn("Org Town Hall", names)
        self.assertIn("Group A Workshop", names)
        self.assertIn("Track A Webinar", names)
        self.assertNotIn("Group B Workshop", names)
        self.assertNotIn("Track B Webinar", names)

    def test_outsider_sees_only_untargeted(self):
        # No groups, no tracks → only events with no targeting on any
        # axis. Locks the "events are pushed" model: outsiders can't
        # browse the targeted catalog.
        names = self._list(user=self.outsider)
        self.assertIn("Org Town Hall", names)
        self.assertNotIn("Group A Workshop", names)
        self.assertNotIn("Group B Workshop", names)
        self.assertNotIn("Track A Webinar", names)
        self.assertNotIn("Track B Webinar", names)

    def test_invited_user_sees_targeted_event_regardless_of_membership(self):
        # Outsider is not in group_b, but an admin invited them. The
        # gate honors explicit invites, so the event must surface.
        EventRsvp.objects.create(
            event=self.event_for_group_b,
            user=self.outsider,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )
        names = self._list(user=self.outsider)
        self.assertIn("Group B Workshop", names)

    # ----- Anonymous --------------------------------------------------

    def test_anonymous_sees_only_untargeted(self):
        # Same shape as the outsider case but exercises the
        # ``not user.is_authenticated`` branch of
        # ``visible_events_queryset``. Public Events page stays
        # functional but doesn't leak targeted internal events.
        names = self._list(user=None)
        self.assertIn("Org Town Hall", names)
        self.assertNotIn("Group A Workshop", names)
        self.assertNotIn("Track B Webinar", names)

    # ----- Track Admin scope ------------------------------------------

    def test_track_admin_sees_their_tracks_events_and_untargeted(self):
        # Track Admin A:
        #   ✓ untargeted (admins still see org-wide announcements)
        #   ✓ event_for_group_a (group's parent track is track_a)
        #   ✓ event_for_track_a (direct FK)
        #   ✗ event_for_group_b (different track scope)
        #   ✗ event_for_track_b (different track scope)
        names = self._list(user=self.track_admin_a)
        self.assertIn("Org Town Hall", names)
        self.assertIn("Group A Workshop", names)
        self.assertIn("Track A Webinar", names)
        self.assertNotIn("Group B Workshop", names)
        self.assertNotIn("Track B Webinar", names)

    # ----- Global Admin -----------------------------------------------

    def test_global_admin_sees_every_event(self):
        # Sanity: ``is_staff=True`` gets ``admin_track_ids=None`` ⇒
        # no clamp at all.
        names = self._list(user=self.global_admin)
        self.assertEqual(
            names,
            {
                "Org Town Hall",
                "Group A Workshop",
                "Group B Workshop",
                "Track A Webinar",
                "Track B Webinar",
            },
        )
