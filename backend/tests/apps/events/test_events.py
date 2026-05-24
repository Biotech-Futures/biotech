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
    - POST works for operational admins only
    - POST rejected for regular user
    - Validation rules (end time after start time)
    """

    def setUp(self):
        # Create regular and admin users
        self.user = User.objects.create_user(email="user2@gmail.com", password="pass123")
        self.admin = User.objects.create_user(email="test_admin@gmail.com", password="admin123")
        AdminScope.objects.create(user=self.admin, is_global=True)

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
        """Operational admin user can POST successfully"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Admin Created Event",
            "description": "By admin",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "event_format": "in_person",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Events.objects.filter(event_name="Admin Created Event").exists())

    def test_non_admin_cannot_create_event(self):
        """Regular user cannot POST"""
        self.client.force_authenticate(user=self.user)
        data = {
            "event_name": "Admin Created Event",
            "description": "By admin",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "event_format": "in_person",
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
            "event_format": "in_person",
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
            "event_format": "in_person",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_datetime", str(response.data))
        self.assertIn("Cannot create events in the past", str(response.data))


class EventListFiltersAndSearchTests(APITestCase):
    """Tests for FE-page additions to ``GET /events/v1/``:

      - ``?rsvp_status=`` filter (single or comma-separated)
      - ``?category=`` filter (maps to ``event_type``)
      - ``?search=`` over event_name / description
      - ``?page_size=`` honored by the list pagination
      - ``"accepted": bool`` field on every row
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
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )

    # ----- ?rsvp_status= filter ---------------------------------------

    def test_rsvp_status_accepted_returns_only_accepted_rsvps(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=accepted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    def test_rsvp_status_multi_value_unions_statuses(self):
        # User: accepted on workshop, declined on webinar.
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=accepted,declined")
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {self.workshop.id, self.webinar.id})

    def test_rsvp_status_tentative_excludes_other_statuses(self):
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.TENTATIVE,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=tentative")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.webinar.id])

    def test_anonymous_rsvp_status_returns_empty(self):
        response = self.client.get(self.url + "?rsvp_status=accepted")
        self.assertEqual(response.data["results"], [])

    def test_invalid_rsvp_status_returns_empty(self):
        # Unknown values must NOT silently turn into "all events".
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=going")
        self.assertEqual(response.data["results"], [])

    def test_declined_rsvp_not_treated_as_accepted(self):
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=accepted")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.workshop.id])

    # ----- registered field on every row ------------------------------

    def test_accepted_field_true_for_user_rsvps(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        rows = {row["id"]: row for row in response.data["results"]}
        self.assertTrue(rows[self.workshop.id]["accepted"])
        self.assertFalse(rows[self.webinar.id]["accepted"])
        self.assertFalse(rows[self.networking.id]["accepted"])

    def test_accepted_field_false_for_anonymous(self):
        response = self.client.get(self.url)
        for row in response.data["results"]:
            self.assertFalse(row["accepted"])

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

    def test_search_combines_with_rsvp_status_filter(self):
        # ``self.user`` has accepted the workshop only. Search +
        # ?rsvp_status=accepted should still narrow correctly.
        self.client.force_authenticate(user=self.user)
        positive = self.client.get(self.url + "?search=workshop&rsvp_status=accepted")
        self.assertEqual([row["id"] for row in positive.data["results"]], [self.workshop.id])

        negative = self.client.get(self.url + "?search=networking&rsvp_status=accepted")
        self.assertEqual(negative.data["results"], [])

    # ----- pagination via ?page_size ----------------------------------

    def test_page_size_query_param_is_honored(self):
        # Cursor pagination returns results + next/previous links but no
        # total ``count`` — verify the page is sized and that more pages
        # exist by following ``next``.
        response = self.client.get(self.url + "?page_size=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertTrue(response.data.get("next"))

    def test_page_size_above_max_is_capped(self):
        # ``EventPagination.max_page_size = 100``; asking for more
        # should not error and must still return at most 100 rows.
        response = self.client.get(self.url + "?page_size=999")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data["results"]), 100)

    def test_pending_rsvp_not_treated_as_accepted(self):
        # PENDING must not surface as accepted=true on the row, and
        # ?rsvp_status=accepted must not return PENDING events.
        # ``responded_at`` is left NULL because the model's check
        # constraint forbids a timestamp on a PENDING row.
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )
        self.client.force_authenticate(user=self.user)

        filtered = self.client.get(self.url + "?rsvp_status=accepted")
        self.assertEqual(
            [row["id"] for row in filtered.data["results"]],
            [self.workshop.id],
        )

        listing = self.client.get(self.url)
        rows = {row["id"]: row for row in listing.data["results"]}
        self.assertFalse(rows[self.webinar.id]["accepted"])

    def test_tentative_rsvp_not_treated_as_accepted(self):
        EventRsvp.objects.create(
            event=self.webinar,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.TENTATIVE,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url + "?rsvp_status=accepted")
        self.assertEqual(
            [row["id"] for row in response.data["results"]],
            [self.workshop.id],
        )


# ---------------------------------------------------------------------------
# Role-model visibility gate.
#
# Per the Roles & Permissions structure, events are pushed by admins
# and users RSVP to events they're targeted by — they don't self-add
# to arbitrary events. These tests exercise the gate against
# ``POST /events/v1/{id}/rsvp/``.
# ---------------------------------------------------------------------------


class EventRsvpVisibilityGateTests(APITestCase):
    """Permission-gate behavior for ``POST /events/v1/{id}/rsvp/``.

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
        return f"/events/v1/{event_id}/rsvp/"

    def _accept_payload(self):
        return {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED}

    def test_untargeted_event_is_open_to_any_authenticated_user(self):
        # An event with no targets is platform-wide; any logged-in
        # user can RSVP.
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(
            self._url(self.untargeted_event.id),
            self._accept_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_of_target_group_can_rsvp(self):
        # ``self.user`` IS a member of group_a, the event's only target.
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.event_for_group_a.id),
            self._accept_payload(),
            format="json",
        )
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
        response = self.client.post(
            self._url(self.event_for_group_b.id),
            self._accept_payload(),
            format="json",
        )
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
        response = self.client.post(
            self._url(self.event_for_group_b.id),
            self._accept_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rsvp = EventRsvp.objects.get(
            event=self.event_for_group_b, user=self.user
        )
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.ACCEPTED)


# ---------------------------------------------------------------------------
# Full user-side RSVP control: ``POST /events/v1/{id}/rsvp/``.
# ---------------------------------------------------------------------------


class EventRsvpSetActionTests(APITestCase):
    """End-to-end coverage for the ``/rsvp/`` endpoint.

    Visibility-gate behavior is covered in
    ``EventRsvpVisibilityGateTests`` above; these tests focus on the
    bits unique to ``/rsvp/`` — accepting going/maybe/declined,
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

    def test_user_can_rsvp_accepted(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.ACCEPTED)
        self.assertIsNotNone(response.data["responded_at"])

        rsvp = EventRsvp.objects.get(event=self.future_event, user=self.user)
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.ACCEPTED)

    def test_user_can_rsvp_tentative(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.TENTATIVE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.TENTATIVE)

    def test_user_can_rsvp_declined(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.DECLINED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rsvp_status"], EventRsvp.RsvpStatus.DECLINED)

    def test_status_transitions_update_in_place(self):
        # accepted → tentative → declined → going. Each call updates the
        # row in place; we never end up with multiple RSVPs for the
        # same (event, user) pair.
        self.client.force_authenticate(user=self.user)
        for new_status in [
            EventRsvp.RsvpStatus.ACCEPTED,
            EventRsvp.RsvpStatus.TENTATIVE,
            EventRsvp.RsvpStatus.DECLINED,
            EventRsvp.RsvpStatus.ACCEPTED,
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
            {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvp_missing_event_returns_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(999999),
            {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_rsvp_is_rejected(self):
        response = self.client.post(
            self._url(self.future_event.id),
            {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )

    def test_rsvp_endpoint_blocks_non_targets(self):
        # Seed a targeted event the user is NOT a member of, then try
        # ``/rsvp/`` — must be 403.
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
        rsvp_resp = self.client.post(
            f"/events/v1/{targeted_event.id}/rsvp/",
            {"rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(rsvp_resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Gap 1: write-side admin-scope enforcement on ``POST /events/v1/``.
#
# The role spec says Track Administrators have access *only* to their
# assigned tracks. The previous ``IsAdminOrReadOnly`` permission checked
# Django's staff flag only, so Track Admins defined by ``AdminScope`` rows
# were locked out of event creation
# entirely. The new ``EventManagePermission`` + ``perform_create``
# track-scope check open the door for Track Admins while keeping the
# scope narrow:
#
#   * Track Admin → may create events whose ``track`` FK is in their
#     scope. Cannot create untargeted events (those reach every user
#     and would be a privilege escalation past their assigned tracks).
#   * Global Admin (``AdminScope.is_global`` row) → unrestricted
#     (any track or untargeted).
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
        body = {
            "event_name": name,
            "description": "fixture",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "event_format": "in_person",
        }
        if track_id is not None:
            body["track"] = track_id
        return body

    # ----- Track Admin happy path -------------------------------------

    def test_track_admin_can_create_event_in_their_track(self):
        # The whole point of Gap 1: Track Admin A creates a Track A
        # event, no Django staff flag required.
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
        # non-staff users; this covers a user with no AdminScope row.
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

        # Global admin via AdminScope.
        self.global_admin = User.objects.create_user(
            email="global-admin@test.com", password="pw"
        )
        AdminScope.objects.create(user=self.global_admin, is_global=True)

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
        # Sanity: ``AdminScope(is_global=True)`` gets
        # ``admin_track_ids=None`` and therefore no clamp at all.
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


# ---------------------------------------------------------------------------
# Scoped id filters: ?user= / ?group= / ?track= on GET /events/v1/.
# Each filter is permission-checked against the caller; an unauthorised
# id returns an empty result, never a wider list.
# ---------------------------------------------------------------------------


class EventScopedIdFilterTests(APITestCase):
    """Tests for the user/group/track id filters."""

    url = "/events/v1/"

    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        self.group_a = Groups.objects.create(group_name="Group A", track=self.track_a)
        self.group_b = Groups.objects.create(group_name="Group B", track=self.track_b)

        self.member_a = User.objects.create_user(email="ma@test.com", password="pw")
        GroupMembership.objects.create(
            group=self.group_a,
            user=self.member_a,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        self.outsider = User.objects.create_user(email="out@test.com", password="pw")

        self.track_admin_a = User.objects.create_user(email="taa@test.com", password="pw")
        AdminScope.objects.create(user=self.track_admin_a, track=self.track_a, is_global=False)

        self.global_admin = User.objects.create_user(email="ga@test.com", password="pw")
        AdminScope.objects.create(user=self.global_admin, is_global=True)

        now = timezone.now()
        self.event_for_group_a = Events.objects.create(
            event_name="Group A Workshop",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_a, group=self.group_a)

        self.event_for_group_b = Events.objects.create(
            event_name="Group B Workshop",
            start_datetime=now + timezone.timedelta(days=2),
            ends_datetime=now + timezone.timedelta(days=2, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_b, group=self.group_b)

        self.event_for_track_a = Events.objects.create(
            event_name="Track A Webinar",
            start_datetime=now + timezone.timedelta(days=3),
            ends_datetime=now + timezone.timedelta(days=3, hours=1),
            location="Online",
            track=self.track_a,
        )

    # ----- ?user= filter ---------------------------------------------

    def test_user_filter_self_returns_own_rsvps(self):
        # member_a has accepted the Group A workshop. ?user=<self> works
        # for non-admins.
        EventRsvp.objects.create(
            event=self.event_for_group_a,
            user=self.member_a,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.member_a)
        response = self.client.get(self.url + f"?user={self.member_a.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_user_filter_other_user_blocked_for_non_admin(self):
        # member_a tries to query the global admin's RSVPs — must be
        # silently empty, not 403, not the full list.
        EventRsvp.objects.create(
            event=self.event_for_group_a,
            user=self.global_admin,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.member_a)
        response = self.client.get(self.url + f"?user={self.global_admin.id}")
        self.assertEqual(response.data["results"], [])

    def test_user_filter_admin_can_audit_any_user(self):
        # Global admin queries member_a's RSVPs — allowed.
        EventRsvp.objects.create(
            event=self.event_for_group_a,
            user=self.member_a,
            rsvp_status=EventRsvp.RsvpStatus.TENTATIVE,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(self.url + f"?user={self.member_a.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_user_filter_anonymous_returns_empty(self):
        response = self.client.get(self.url + f"?user={self.member_a.id}")
        self.assertEqual(response.data["results"], [])

    # ----- ?group= filter --------------------------------------------

    def test_group_filter_member_can_query_own_group(self):
        self.client.force_authenticate(user=self.member_a)
        response = self.client.get(self.url + f"?group={self.group_a.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_group_filter_outsider_blocked(self):
        # Outsider has no membership in group_a — silent empty.
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.url + f"?group={self.group_a.id}")
        self.assertEqual(response.data["results"], [])

    def test_group_filter_member_blocked_from_other_group(self):
        # member_a is in group_a but tries ?group=group_b — silent empty.
        self.client.force_authenticate(user=self.member_a)
        response = self.client.get(self.url + f"?group={self.group_b.id}")
        self.assertEqual(response.data["results"], [])

    def test_group_filter_track_admin_limited_to_own_tracks(self):
        # track_admin_a may query group_a (in track_a) but not group_b.
        self.client.force_authenticate(user=self.track_admin_a)
        ok_response = self.client.get(self.url + f"?group={self.group_a.id}")
        self.assertEqual(
            [row["id"] for row in ok_response.data["results"]],
            [self.event_for_group_a.id],
        )
        blocked_response = self.client.get(self.url + f"?group={self.group_b.id}")
        self.assertEqual(blocked_response.data["results"], [])

    def test_group_filter_global_admin_any_group(self):
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(self.url + f"?group={self.group_b.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_b.id])

    # ----- ?track= filter --------------------------------------------

    def test_track_filter_member_can_query_own_track(self):
        # member_a is in group_a (track_a). Track filter returns events
        # touching track_a: the direct-FK one and the group-targeted one.
        self.client.force_authenticate(user=self.member_a)
        response = self.client.get(self.url + f"?track={self.track_a.id}")
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(
            ids,
            {self.event_for_group_a.id, self.event_for_track_a.id},
        )

    def test_track_filter_outsider_blocked(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.url + f"?track={self.track_a.id}")
        self.assertEqual(response.data["results"], [])

    def test_track_filter_track_admin_blocked_from_other_track(self):
        self.client.force_authenticate(user=self.track_admin_a)
        response = self.client.get(self.url + f"?track={self.track_b.id}")
        self.assertEqual(response.data["results"], [])

    def test_track_filter_global_admin_any_track(self):
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(self.url + f"?track={self.track_b.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_b.id])


# ---------------------------------------------------------------------------
# Supervisor scope on the scoped id filters.
#
# A supervisor's view scope = self ∪ supervisees ∪ mentors of those
# supervisees' groups. Tested across ?user= / ?group= / ?track=.
# ---------------------------------------------------------------------------


class EventSupervisorScopeFilterTests(APITestCase):
    """Supervisor scope on ?user= / ?group= / ?track=."""

    url = "/events/v1/"

    def setUp(self):
        from apps.users.models import StudentProfile, SupervisorProfile

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        self.group_a = Groups.objects.create(group_name="Group A", track=self.track_a)
        self.group_b = Groups.objects.create(group_name="Group B", track=self.track_b)

        # Supervisor and a profile row so StudentProfile.supervisor FK resolves.
        self.supervisor = User.objects.create_user(email="sup@test.com", password="pw")
        self.supervisor_profile = SupervisorProfile.objects.create(
            user=self.supervisor, school_name="Test School"
        )

        # A second supervisor (negative case for isolation).
        self.other_supervisor = User.objects.create_user(email="sup2@test.com", password="pw")
        SupervisorProfile.objects.create(user=self.other_supervisor, school_name="Test School")

        # Student supervised by self.supervisor; member of group_a.
        self.student = User.objects.create_user(email="stu@test.com", password="pw")
        StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Q",
            pg_last_name="W",
            school_name="Test School",
            year_lvl="10",
            supervisor=self.supervisor_profile,
        )
        GroupMembership.objects.create(
            group=self.group_a,
            user=self.student,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        # Mentor of group_a (in the supervisor's reach via the supervisee).
        self.mentor = User.objects.create_user(email="men@test.com", password="pw")
        GroupMembership.objects.create(
            group=self.group_a,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        # Mentor of group_b (NOT in scope — different group, no supervisee there).
        self.outside_mentor = User.objects.create_user(email="omn@test.com", password="pw")
        GroupMembership.objects.create(
            group=self.group_b,
            user=self.outside_mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        # Unrelated student (no relationship to self.supervisor).
        self.outsider_student = User.objects.create_user(email="osu@test.com", password="pw")
        StudentProfile.objects.create(
            user=self.outsider_student,
            pg_first_name="O",
            pg_last_name="S",
            school_name="Test School",
            year_lvl="10",
        )
        GroupMembership.objects.create(
            group=self.group_b,
            user=self.outsider_student,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        now = timezone.now()
        self.event_for_group_a = Events.objects.create(
            event_name="Group A Event",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_a, group=self.group_a)

        self.event_for_group_b = Events.objects.create(
            event_name="Group B Event",
            start_datetime=now + timezone.timedelta(days=2),
            ends_datetime=now + timezone.timedelta(days=2, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=self.event_for_group_b, group=self.group_b)

        # Seed RSVPs we will look up via ?user=.
        EventRsvp.objects.create(
            event=self.event_for_group_a,
            user=self.student,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )
        EventRsvp.objects.create(
            event=self.event_for_group_a,
            user=self.mentor,
            rsvp_status=EventRsvp.RsvpStatus.TENTATIVE,
            responded_at=timezone.now(),
        )
        EventRsvp.objects.create(
            event=self.event_for_group_b,
            user=self.outside_mentor,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )

    # ----- ?user= ----------------------------------------------------

    def test_supervisor_can_query_supervisee_user(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?user={self.student.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_supervisor_can_query_mentor_of_supervisee_group(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?user={self.mentor.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_supervisor_blocked_from_unrelated_user(self):
        # outside_mentor is a mentor of group_b, no supervisee there.
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?user={self.outside_mentor.id}")
        self.assertEqual(response.data["results"], [])

    def test_other_supervisor_cannot_query_unrelated_supervisee(self):
        # `other_supervisor` does not supervise anyone.
        self.client.force_authenticate(user=self.other_supervisor)
        response = self.client.get(self.url + f"?user={self.student.id}")
        self.assertEqual(response.data["results"], [])

    # ----- ?group= ---------------------------------------------------

    def test_supervisor_can_query_group_containing_supervisee(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?group={self.group_a.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_supervisor_blocked_from_unrelated_group(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?group={self.group_b.id}")
        self.assertEqual(response.data["results"], [])

    # ----- ?track= ---------------------------------------------------

    def test_supervisor_can_query_track_of_supervisee_group(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?track={self.track_a.id}")
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.event_for_group_a.id])

    def test_supervisor_blocked_from_unrelated_track(self):
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url + f"?track={self.track_b.id}")
        self.assertEqual(response.data["results"], [])


# ---------------------------------------------------------------------------
# Detail / update / destroy on EventViewSet, the ?when= filter, targeting
# fields on create+update, and the bulk-invite endpoint. Each class builds
# its own minimal world rather than sharing a fixture so failures point at
# the surface they belong to.
# ---------------------------------------------------------------------------


class EventDetailAndDestroyTests(APITestCase):
    """GET/PATCH/DELETE /events/v1/{id}/."""

    def setUp(self):
        self.admin = User.objects.create_user(email="d-admin@t.com", password="pw")
        AdminScope.objects.create(user=self.admin, is_global=True)
        self.user = User.objects.create_user(email="d-user@t.com", password="pw")
        now = timezone.now()
        self.event = Events.objects.create(
            event_name="Detail Event",
            description="x",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )

    def _url(self, pk):
        return f"/events/v1/{pk}/"

    def test_authenticated_user_can_retrieve_visible_event(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self._url(self.event.id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["id"], self.event.id)

    def test_admin_can_patch_event(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(self._url(self.event.id), {"event_name": "Renamed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertEqual(self.event.event_name, "Renamed")

    def test_non_admin_patch_blocked(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.patch(self._url(self.event.id), {"event_name": "Renamed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_soft_delete(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.delete(self._url(self.event.id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.deleted_at)

    def test_admin_can_restore_soft_deleted_event(self):
        # Restore clears deleted_at and returns the normal event serializer shape.
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._url(self.event.id))

        r = self.client.post(f"/events/v1/{self.event.id}/restore/")

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.deleted_at)
        self.assertIsNone(r.data["deleted_at"])

    def test_deleted_filter_lists_deleted_events_for_admin(self):
        # deleted=true is the admin recovery list for events.
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._url(self.event.id))

        r = self.client.get("/events/v1/?deleted=true&when=all")

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in r.data["results"]]
        self.assertEqual(ids, [self.event.id])

    def test_api_v1_mount_lists_and_restores_deleted_events(self):
        # The canonical frontend/admin route must expose the same recovery flow
        # as the legacy /events/v1/... endpoint.
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._url(self.event.id))

        listed = self.client.get("/api/v1/events/?deleted=true&when=all")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in listed.data["results"]], [self.event.id])

        restored = self.client.post(f"/api/v1/events/{self.event.id}/restore/")
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.deleted_at)
        self.assertIsNone(restored.data["deleted_at"])

    def test_re_delete_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._url(self.event.id))
        r = self.client.delete(self._url(self.event.id))
        # The visibility queryset filters soft-deleted, so a re-DELETE
        # 404s. Clients should treat the first 200 as authoritative.
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class EventWhenFilterTests(APITestCase):
    """?when=upcoming (default) | past | all on the list endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(email="when@t.com", password="pw")
        now = timezone.now()
        self.upcoming = Events.objects.create(
            event_name="Upcoming",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        self.past = Events.objects.create(
            event_name="Past",
            start_datetime=now - timezone.timedelta(days=2),
            ends_datetime=now - timezone.timedelta(days=2) + timezone.timedelta(hours=1),
            location="Online",
        )
        self.client.force_authenticate(user=self.user)

    def test_default_returns_upcoming_only(self):
        r = self.client.get("/events/v1/")
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.upcoming.id, ids)
        self.assertNotIn(self.past.id, ids)

    def test_when_past_returns_past_only(self):
        r = self.client.get("/events/v1/?when=past")
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.past.id, ids)
        self.assertNotIn(self.upcoming.id, ids)

    def test_when_all_returns_both(self):
        r = self.client.get("/events/v1/?when=all")
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.past.id, ids)
        self.assertIn(self.upcoming.id, ids)

    def test_unknown_when_falls_back_to_upcoming(self):
        r = self.client.get("/events/v1/?when=garbage")
        ids = {row["id"] for row in r.data["results"]}
        self.assertNotIn(self.past.id, ids)


class EventTargetingTests(APITestCase):
    """target_group_ids / target_track_ids on create + PATCH."""

    def setUp(self):
        self.admin = User.objects.create_user(email="t-admin@t.com", password="pw")
        AdminScope.objects.create(user=self.admin, is_global=True)
        country = Countries.objects.create(country_name="X")
        state = CountryStates.objects.create(country=country, state_name="Y")
        self.track_a = Tracks.objects.create(track_name="A", state=state)
        self.track_b = Tracks.objects.create(track_name="B", state=state)
        self.group_a = Groups.objects.create(group_name="GA", track=self.track_a)
        self.client.force_authenticate(user=self.admin)

    def _payload(self, **overrides):
        now = timezone.now()
        body = {
            "event_name": "Targeted",
            "start_datetime": (now + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            "event_format": "virtual",
        }
        body.update(overrides)
        return body

    def test_create_with_target_groups_persists_rows(self):
        r = self.client.post(
            "/events/v1/",
            self._payload(target_group_ids=[self.group_a.id]),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(
            list(EventTargetGroup.objects.filter(event_id=r.data["id"]).values_list("group_id", flat=True)),
            [self.group_a.id],
        )

    def test_patch_replaces_target_set(self):
        event = Events.objects.create(
            event_name="Existing",
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            ends_datetime=timezone.now() + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=event, group=self.group_a)
        r = self.client.patch(
            f"/events/v1/{event.id}/",
            {"target_group_ids": []},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(EventTargetGroup.objects.filter(event=event).exists())

    def test_patch_omitting_field_leaves_targets_unchanged(self):
        event = Events.objects.create(
            event_name="Existing",
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            ends_datetime=timezone.now() + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        EventTargetGroup.objects.create(event=event, group=self.group_a)
        r = self.client.patch(
            f"/events/v1/{event.id}/",
            {"event_name": "Renamed only"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertTrue(EventTargetGroup.objects.filter(event=event, group=self.group_a).exists())


class EventBulkInviteTests(APITestCase):
    """POST /events/v1/{id}/rsvp/bulk/."""

    def setUp(self):
        self.admin = User.objects.create_user(email="bi-admin@t.com", password="pw")
        AdminScope.objects.create(user=self.admin, is_global=True)
        self.u1 = User.objects.create_user(email="bi1@t.com", password="pw")
        self.u2 = User.objects.create_user(email="bi2@t.com", password="pw")
        now = timezone.now()
        self.event = Events.objects.create(
            event_name="Bulk Invite Event",
            start_datetime=now + timezone.timedelta(days=1),
            ends_datetime=now + timezone.timedelta(days=1, hours=1),
            location="Online",
        )
        self.client.force_authenticate(user=self.admin)

    def _url(self):
        return f"/events/v1/{self.event.id}/rsvp/bulk/"

    def test_bulk_invite_creates_rows(self):
        r = self.client.post(
            self._url(),
            {"user_ids": [self.u1.id, self.u2.id]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(set(r.data["created"]), {self.u1.id, self.u2.id})
        self.assertEqual(r.data["not_found"], [])
        self.assertEqual(
            EventRsvp.objects.filter(event=self.event).count(),
            2,
        )

    def test_bulk_invite_reports_unknown_user_ids(self):
        r = self.client.post(
            self._url(),
            {"user_ids": [self.u1.id, 999999]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIn(999999, r.data["not_found"])
        self.assertEqual(set(r.data["created"]), {self.u1.id})

    def test_bulk_invite_upsert_updates_existing_row(self):
        EventRsvp.objects.create(
            event=self.event, user=self.u1, rsvp_status=EventRsvp.RsvpStatus.DECLINED
        )
        r = self.client.post(
            self._url(),
            {"user_ids": [self.u1.id], "rsvp_status": EventRsvp.RsvpStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["updated"], [self.u1.id])
        self.u1_rsvp = EventRsvp.objects.get(event=self.event, user=self.u1)
        self.assertEqual(self.u1_rsvp.rsvp_status, EventRsvp.RsvpStatus.ACCEPTED)

    def test_student_cannot_bulk_invite(self):
        student = User.objects.create_user(email="student-bi@t.com", password="pw")
        self.client.force_authenticate(user=student)
        r = self.client.post(
            self._url(),
            {"user_ids": [self.u1.id]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_user_ids_rejected(self):
        r = self.client.post(self._url(), {"user_ids": []}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
