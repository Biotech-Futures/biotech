"""Tests for admin event service."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

import struct
import tempfile
import zlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.admin.services.event import (
    query_event_by_id, create_event, update_event, delete_event,
    query_event_rsvps, create_event_rsvp, update_event_rsvp,
    query_event_targets, query_groups, query_roles,
)
from apps.events.models import Events, EventRsvp, EventTargetGroup, EventTargetRole
from apps.groups.models import Groups
from apps.resources.models import Roles
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope


class EventServiceTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com", first_name="Host", last_name="User",
            password="testpass",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin)

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
        # Event targeting is group + role only (track targeting was removed).
        group = Groups.objects.create(group_name="Target Group")
        role, _ = Roles.objects.get_or_create(role_name="student")
        EventTargetGroup.objects.create(event=self.event, group=group)
        EventTargetRole.objects.create(event=self.event, role=role)

        result = query_event_targets(str(self.event.id))
        self.assertEqual(result["msg"], "Event targets retrieved successfully")
        self.assertIn(group.id, result["data"]["groupIds"])
        self.assertIn(role.id, result["data"]["roleIds"])

    def test_query_event_targets_invalid_id(self):
        result = query_event_targets("bad")
        self.assertEqual(result["msg"], "Invalid event id")
        self.assertIsNone(result["data"])

    def test_query_event_rsvps(self):
        rsvp = EventRsvp.objects.create(
            event=self.event, user=self.host, rsvp_status="accepted",
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
        result = update_event_rsvp("9999", {"rsvpStatus": "tentative"})
        self.assertEqual(result["msg"], "Event RSVP not found")
        self.assertIsNone(result["data"])

    def test_update_event_rsvp_invalid_id(self):
        result = update_event_rsvp("bad", {})
        self.assertEqual(result["msg"], "Invalid RSVP id")
        self.assertIsNone(result["data"])

    def test_query_groups_reference(self):
        Groups.objects.create(group_name="Ref Group")
        result = query_groups(requesting_user=self.admin)
        group_names = [g["groupName"] for g in result["data"]]
        self.assertIn("Ref Group", group_names)

    def test_query_roles_reference(self):
        Roles.objects.get_or_create(role_name="student")
        Roles.objects.get_or_create(role_name="mentor")
        result = query_roles()
        self.assertGreaterEqual(len(result["data"]), 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="event-image-tests-"))
class EventImageUploadTests(TestCase):
    """The happy path needs a real file, and used to be handed a MagicMock.

    Two separate faults came from that one fixture, and each hid the other:

    * ``upload_event_image`` passes the file to ``storage.save``, which for a
      real upload calls ``open(content.temporary_file_path(), 'rb')``. A
      ``MagicMock``'s ``__index__`` returns 1, so ``open`` treated it as file
      descriptor 1 — the process's own stdout — and closed it. The suite still
      printed ``OK``, then the interpreter could not flush and exited 120.
      That is a failed job in CI, and ``deploy`` needs it, so nothing deployed.
    * Because ``storage.save`` blew up on the mock, the valid-upload test only
      ever exercised the *failure* branch. It asserted the failure message on
      what is supposed to be the success path, and passed for that reason.

    So the fixture is a real PNG and the assertions are the success ones.
    MEDIA_ROOT is redirected to a temp directory: with USE_AZURE_BLOB_STORAGE
    off the save is a genuine write, and it should not land in the repo.

    🔴 The fixture's *dimensions* are load-bearing, which is not obvious.
    It was 1x1 when this was written, on the reasoning that any valid PNG
    would do. That reasoning expires: the client's p40 requires event banners
    to be exactly 1280x320, so an upload that is not that size is going to be
    refused. A 1x1 fixture asserting "this upload succeeds" would then fail,
    and the failure would look like a bug in the gate rather than a stale
    fixture. Generated at the required size instead, so this test keeps
    testing what it means to test.

    Built from zlib rather than loaded from a file or pasted in as bytes:
    Pillow is not a dependency of this project, a binary fixture on disk is a
    thing nobody can read in review, and 883 bytes of escaped PNG in the
    source would hide the two numbers that actually matter. Written this way
    the size is one line, and follows the client's requirement if it changes.
    """

    BANNER_WIDTH = 1280
    BANNER_HEIGHT = 320

    @staticmethod
    def _png(width: int, height: int) -> bytes:
        """A real, decodable PNG of exactly these dimensions.

        Opaque white, 8-bit greyscale, one filter byte per scanline — the
        smallest thing that is still a genuine image rather than a header
        claiming to be one. A reader that checks dimensions must be able to
        get them from this, so the IHDR has to be honest.
        """
        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return (
                struct.pack(">I", len(data))
                + body
                + struct.pack(">I", zlib.crc32(body))
            )

        # width, height, bit depth 8, colour type 0 (greyscale), then the
        # three zero bytes for compression, filter and interlace method.
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
        scanlines = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(scanlines, 9))
            + chunk(b"IEND", b"")
        )

    def setUp(self):
        self.mock_file = SimpleUploadedFile(
            "banner.png",
            self._png(self.BANNER_WIDTH, self.BANNER_HEIGHT),
            content_type="image/png",
        )

    def test_fixture_is_really_a_banner_sized_png(self):
        """The fixture's own size, asserted rather than assumed.

        Without this the generator could start producing something else —
        a wrong struct format, a transposed pair of arguments — and every
        other test here would carry on passing, because none of them look at
        the image. The one test that would eventually catch it is a gate that
        does not exist in this branch yet.

        Read back out of the IHDR the way any reader would: bytes 16-24, the
        two big-endian integers immediately after the chunk's length and tag.
        """
        data = self._png(self.BANNER_WIDTH, self.BANNER_HEIGHT)

        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1280, 320))

    def test_upload_image_valid(self):
        from apps.admin.services.event_image import upload_event_image
        result = upload_event_image(self.mock_file)

        self.assertEqual(result["msg"], "Event image uploaded successfully")
        self.assertIsNotNone(result["data"], result["msg"])
        # The durable key, not a signed URL: the URL is minted fresh on read.
        self.assertTrue(result["data"]["key"].endswith(".png"))

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
