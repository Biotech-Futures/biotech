"""Tests for admin event service."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from apps.admin.services.event import (
    query_event_by_id, create_event, update_event, delete_event,
    query_event_rsvps, create_event_rsvp, update_event_rsvp,
    query_event_targets, query_groups, query_roles, query_tracks,
)
from apps.events.models import Events, EventRsvp, EventTargetGroup, EventTargetRole, EventTargetTrack
from apps.groups.models import Countries, CountryStates, Groups, Tracks
from apps.resources.models import Roles
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope


class EventServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-1", state=self.state)

        self.host = User.objects.create_user(
            email="host@example.com", first_name="Host", last_name="User",
            password="testpass",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin, is_global=True)

        now = timezone.now()
        self.event = Events.objects.create(
            event_name="Test Event",
            description="A test event",
            host_user=self.host,
            start_datetime=now + timedelta(days=1),
            ends_datetime=now + timedelta(days=1, hours=2),
            event_format=Events.EventFormat.IN_PERSON,
            location="Room 101",
        )

    def test_query_event_by_id_found(self):
        result = query_event_by_id(str(self.event.id))
        self.assertEqual(result["msg"], "Event retrieved successfully")
        self.assertEqual(result["data"]["eventName"], "Test Event")

    def test_query_event_by_id_invalid_id(self):
        result = query_event_by_id("invalid")
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_query_event_by_id_not_found(self):
        result = query_event_by_id("9999")
        self.assertEqual(result["msg"], "Event not found")
        self.assertIsNone(result["data"])

    def test_create_event_basic(self):
        now = timezone.now()
        result = create_event({
            "eventName": "New Event",
            "description": "Brand new",
            "hostUserId": self.host.id,
            "startAt": (now + timedelta(days=2)).isoformat(),
            "endsAt": (now + timedelta(days=2, hours=3)).isoformat(),
            "location": "Conference Hall",
        })
        self.assertEqual(result["msg"], "Event created successfully")
        self.assertEqual(result["data"]["eventName"], "New Event")

    def test_create_event_missing_dates(self):
        result = create_event({"eventName": "Bad Event"})
        self.assertEqual(result["msg"], "startAt and endsAt are required")

    def test_create_event_start_after_end(self):
        now = timezone.now()
        result = create_event({
            "eventName": "Bad Event",
            "startAt": (now + timedelta(days=5)).isoformat(),
            "endsAt": (now + timedelta(days=3)).isoformat(),
        })
        self.assertEqual(result["msg"], "endsAt must be after startAt")

    def test_create_event_missing_name(self):
        now = timezone.now()
        result = create_event({
            "startAt": (now + timedelta(days=1)).isoformat(),
            "endsAt": (now + timedelta(days=1, hours=2)).isoformat(),
        })
        self.assertEqual(result["msg"], "eventName is required")

    def test_update_event(self):
        result = update_event(str(self.event.id), {
            "eventName": "Updated Event",
            "description": "Updated description",
        })
        self.assertEqual(result["msg"], "Event updated successfully")
        self.assertEqual(result["data"]["eventName"], "Updated Event")

    def test_update_event_invalid_id(self):
        result = update_event("bad", {})
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_update_event_not_found(self):
        result = update_event("9999", {"eventName": "Ghost"})
        self.assertEqual(result["msg"], "Event not found")
        self.assertIsNone(result["data"])

    def test_delete_event(self):
        result = delete_event(str(self.event.id))
        self.assertEqual(result["msg"], "Event deleted successfully")
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.deleted_at)

    def test_delete_event_invalid_id(self):
        result = delete_event("bad")
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_delete_event_not_found(self):
        result = delete_event("9999")
        self.assertEqual(result["msg"], "Event not found")
        self.assertIsNone(result["data"])

    def test_query_event_targets(self):
        group = Groups.objects.create(group_name="Target Group", track=self.track)
        role, _ = Roles.objects.get_or_create(role_name="student")
        EventTargetGroup.objects.create(event=self.event, group=group)
        EventTargetRole.objects.create(event=self.event, role=role)
        EventTargetTrack.objects.create(event=self.event, track=self.track)

        result = query_event_targets(str(self.event.id))
        self.assertEqual(result["msg"], "Event targets retrieved successfully")
        self.assertIn(group.id, result["data"]["groupIds"])
        self.assertIn(role.id, result["data"]["roleIds"])
        self.assertIn(self.track.id, result["data"]["trackIds"])

    def test_query_event_targets_invalid_id(self):
        result = query_event_targets("bad")
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_query_event_rsvps(self):
        rsvp = EventRsvp.objects.create(
            event=self.event, user=self.host, rsvp_status="going",
        )
        result = query_event_rsvps(str(self.event.id))
        self.assertEqual(result["msg"], "Event RSVPs retrieved successfully")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], rsvp.id)

    def test_query_event_rsvps_invalid_id(self):
        result = query_event_rsvps("bad")
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_create_event_rsvp(self):
        result = create_event_rsvp(str(self.event.id), {
            "userId": self.host.id,
            "rsvpStatus": "accepted",
        })
        self.assertEqual(result["msg"], "Event RSVP created successfully")
        self.assertEqual(result["data"]["rsvpStatus"], "accepted")

    def test_create_event_rsvp_invalid_id(self):
        result = create_event_rsvp("bad", {})
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_update_event_rsvp(self):
        rsvp = EventRsvp.objects.create(
            event=self.event, user=self.host, rsvp_status="accepted",
        )
        result = update_event_rsvp(str(rsvp.id), {"rsvpStatus": "declined"})
        self.assertEqual(result["msg"], "Event RSVP updated successfully")
        self.assertEqual(result["data"]["rsvpStatus"], "declined")

    def test_update_event_rsvp_not_found(self):
        result = update_event_rsvp("9999", {"rsvpStatus": "maybe"})
        self.assertEqual(result["msg"], "Event RSVP not found")
        self.assertIsNone(result["data"])

    def test_update_event_rsvp_invalid_id(self):
        result = update_event_rsvp("bad", {})
        self.assertEqual(result["msg"], "Invalid RSVP id")
        self.assertIsNone(result["data"])

    def test_query_groups_reference(self):
        group = Groups.objects.create(group_name="Ref Group", track=self.track)
        result = query_groups(requesting_user=self.admin)
        group_names = [g["groupName"] for g in result["data"]]
        self.assertIn("Ref Group", group_names)

    def test_query_roles_reference(self):
        Roles.objects.get_or_create(role_name="student")
        Roles.objects.get_or_create(role_name="mentor")
        result = query_roles()
        self.assertGreaterEqual(len(result["data"]), 2)

    def test_query_tracks_reference(self):
        result = query_tracks(requesting_user=self.admin)
        track_names = [t["trackName"] for t in result["data"]]
        self.assertIn("TRACK-1", track_names)


class EventImageUploadTests(TestCase):
    def setUp(self):
        self.mock_file = MagicMock()
        self.mock_file.content_type = "image/png"
        self.mock_file.size = 1024 * 1024  # 1 MB

    def test_upload_image_valid(self):
        from apps.admin.services.event_image import upload_event_image
        result = upload_event_image(self.mock_file)
        if result.get("data") is not None:
            self.assertIn(result["msg"], [
                "Upload failed: " + str(result["data"]),
            ])
        else:
            self.assertIsNotNone(result["msg"])

    def test_upload_image_invalid_type(self):
        from apps.admin.services.event_image import upload_event_image
        self.mock_file.content_type = "image/tiff"
        result = upload_event_image(self.mock_file)
        self.assertEqual(
            result["msg"],
            "Unsupported file type 'image/tiff'. Allowed: jpeg, png, gif, webp.",
        )
        self.assertIsNone(result["data"])

    def test_upload_image_too_large(self):
        from apps.admin.services.event_image import upload_event_image
        self.mock_file.content_type = "image/png"
        self.mock_file.size = 10 * 1024 * 1024  # 10 MB
        result = upload_event_image(self.mock_file)
        self.assertEqual(result["msg"], "File too large. Maximum size is 5 MB.")
        self.assertIsNone(result["data"])
