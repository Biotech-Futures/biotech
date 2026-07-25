"""Event banner images: store a durable blob key, sign a fresh URL on read.

Regression cover for the bug where a 1-hour Azure SAS URL was persisted into
event_image and the image stopped loading once the signature expired.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import serializers

from apps.admin.services.event import create_event, query_event_by_id
from apps.events.image_storage import (
    extract_event_image_key,
    reset_event_image_storage_cache,
    resolve_event_image_url,
)
from apps.events.models import Events
from apps.events.serializers import EventSerializer
from apps.users.models import User

_OUR_HOST = "acct.blob.core.windows.net"
_SIGNED_URL = f"https://{_OUR_HOST}/media/abc123.png?se=2020-01-01T00:00:00Z&sp=r&sig=ZZZ"
_EXTERNAL_URL = "https://cdn.example.com/banner.png"


@override_settings(AZURE_ACCOUNT_NAME="acct", AZURE_CUSTOM_DOMAIN=_OUR_HOST)
class ExtractEventImageKeyTests(TestCase):
    def test_none_and_blank(self):
        self.assertIsNone(extract_event_image_key(None))
        self.assertIsNone(extract_event_image_key(""))
        self.assertIsNone(extract_event_image_key("   "))

    def test_our_signed_url_is_reduced_to_key(self):
        # Signature stripped so an edit round-trip can't re-persist an expiring link.
        self.assertEqual(extract_event_image_key(_SIGNED_URL), "abc123.png")

    def test_external_url_is_left_alone(self):
        self.assertEqual(extract_event_image_key(_EXTERNAL_URL), _EXTERNAL_URL)

    def test_bare_key_is_left_alone(self):
        self.assertEqual(extract_event_image_key("abc123.png"), "abc123.png")

    def test_traversal_and_cross_blob_values_are_rejected(self):
        # Crafted values that would otherwise get a valid signature minted for an
        # arbitrary blob in the shared `media` container.
        for bad in [
            f"https://{_OUR_HOST}/media/../resources/secret.pdf",  # traversal
            f"https://{_OUR_HOST}/media/resources/secret.png",     # nested path
            f"https://{_OUR_HOST}/resources/secret.png",           # other prefix
            f"https://{_OUR_HOST}/media/secret.pdf",               # non-image ext
            "resources/secret.png",                                 # bare nested path
            "secret.pdf",                                           # bare non-image
            "javascript:alert(1)",                                  # bad scheme
        ]:
            self.assertIsNone(extract_event_image_key(bad), bad)


@override_settings(AZURE_ACCOUNT_NAME="acct", AZURE_CUSTOM_DOMAIN=_OUR_HOST)
class ResolveEventImageUrlTests(TestCase):
    def setUp(self):
        reset_event_image_storage_cache()
        self.addCleanup(reset_event_image_storage_cache)

    def test_none(self):
        self.assertIsNone(resolve_event_image_url(None))
        self.assertIsNone(resolve_event_image_url(""))

    def test_bare_key_is_signed(self):
        # USE_AZURE_BLOB_STORAGE is False in tests → local backend yields a media path.
        url = resolve_event_image_url("abc123.png")
        self.assertTrue(url.endswith("/media/event-images/abc123.png"), url)

    def test_legacy_signed_url_is_re_resolved(self):
        # Stale SAS URL recovers: key is extracted, then a fresh URL is minted.
        url = resolve_event_image_url(_SIGNED_URL)
        self.assertTrue(url.endswith("/media/event-images/abc123.png"), url)

    def test_external_url_passes_through(self):
        self.assertEqual(resolve_event_image_url(_EXTERNAL_URL), _EXTERNAL_URL)

    def test_unsafe_values_are_not_signed(self):
        # Never mint a signature for a traversal / cross-blob / non-image target.
        for bad in [
            f"https://{_OUR_HOST}/media/../secret.png",
            f"https://{_OUR_HOST}/media/secret.pdf",
            f"https://{_OUR_HOST}/resources/secret.png",
            "resources/secret.png",
            "../secret.png",
        ]:
            self.assertIsNone(resolve_event_image_url(bad), bad)


@override_settings(AZURE_ACCOUNT_NAME="acct", AZURE_CUSTOM_DOMAIN=_OUR_HOST)
class EventImageWriteReadTests(TestCase):
    def setUp(self):
        reset_event_image_storage_cache()
        self.addCleanup(reset_event_image_storage_cache)
        self.host = User.objects.create_user(email="host@example.com", password="x")

    def _times(self):
        start = timezone.now() + timedelta(days=1)
        return start.isoformat(), (start + timedelta(hours=1)).isoformat()

    def test_create_event_persists_key_and_reads_fresh_url(self):
        start, ends = self._times()
        result = create_event({
            "eventName": "Launch",
            "startAt": start,
            "endsAt": ends,
            "hostUserId": self.host.id,
            "eventImage": _SIGNED_URL,
        })
        event = Events.objects.get(id=result["data"]["id"])
        # Stored durably as a key, not the expiring signed URL.
        self.assertEqual(event.event_image, "abc123.png")
        # Read resolves to a usable URL.
        read = query_event_by_id(str(event.id))
        self.assertTrue(read["data"]["eventImage"].endswith("/media/event-images/abc123.png"))

    def test_serializer_output_resolves_stored_key(self):
        start = timezone.now() + timedelta(days=1)
        event = Events.objects.create(
            event_name="Launch",
            start_datetime=start,
            ends_datetime=start + timedelta(hours=1),
            event_image="abc123.png",
        )
        data = EventSerializer(event).data
        self.assertTrue(data["event_image"].endswith("/media/event-images/abc123.png"))

    def test_serializer_validate_normalizes_and_rejects_bad_scheme(self):
        ser = EventSerializer()
        self.assertEqual(ser.validate_event_image(_SIGNED_URL), "abc123.png")
        self.assertEqual(ser.validate_event_image(_EXTERNAL_URL), _EXTERNAL_URL)
        self.assertIsNone(ser.validate_event_image(""))
        with self.assertRaises(serializers.ValidationError):
            ser.validate_event_image("javascript:alert(1)")
